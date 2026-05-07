"""
FastAPI application for multi-agent workflow system.
Endpoints: POST /task, GET /task/{id}, POST /checkpoint/{id}/approve
"""
import uuid
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import structlog

from app.config import settings
from app.models import (
    TaskRequest, TaskResponse, TaskStatus,
    CheckpointEditRequest, HealthResponse
)
from app.supervisor import SupervisorAgent

logger = structlog.get_logger()

# In-memory task store (replace with Redis in production)
task_store: dict[str, TaskStatus] = {}
supervisors: dict[str, SupervisorAgent] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting multi-agent workflow API", version="1.0.0")
    yield
    logger.info("Shutting down multi-agent workflow API")


app = FastAPI(
    title="Victor Multi-Agent Workflow",
    description="Production multi-agent AI system using Anthropic Claude",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")


@app.post("/task", response_model=TaskResponse, status_code=202)
async def submit_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
):
    """
    Submit a complex task for multi-agent processing.
    Returns task_id immediately; poll /task/{task_id} for status.
    """
    task_id = str(uuid.uuid4())
    status = TaskStatus(
        task_id=task_id,
        status="queued",
        task=request.task,
    )
    task_store[task_id] = status

    supervisor = SupervisorAgent(
        task_id=task_id,
        task_store=task_store,
        require_approval=request.require_approval,
    )
    supervisors[task_id] = supervisor

    background_tasks.add_task(supervisor.run, request.task)

    logger.info("Task submitted", task_id=task_id, task=request.task[:100])
    return TaskResponse(task_id=task_id, status="queued")


@app.get("/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Poll task status and partial results."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_store[task_id]


@app.get("/task/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE stream of agent reasoning steps."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")

    supervisor = supervisors.get(task_id)
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found")

    async def event_generator():
        async for event in supervisor.event_stream():
            yield f"data: {event}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/checkpoint/{checkpoint_id}/approve")
async def approve_checkpoint(checkpoint_id: str):
    """Approve worker output and continue execution."""
    for supervisor in supervisors.values():
        if await supervisor.approve_checkpoint(checkpoint_id):
            return {"status": "approved", "checkpoint_id": checkpoint_id}
    raise HTTPException(status_code=404, detail="Checkpoint not found")


@app.post("/checkpoint/{checkpoint_id}/edit")
async def edit_checkpoint(checkpoint_id: str, request: CheckpointEditRequest):
    """Edit worker output before continuing execution."""
    for supervisor in supervisors.values():
        if await supervisor.edit_checkpoint(checkpoint_id, request.edited_output):
            return {"status": "edited", "checkpoint_id": checkpoint_id}
    raise HTTPException(status_code=404, detail="Checkpoint not found")


@app.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    supervisor = supervisors.get(task_id)
    if supervisor:
        await supervisor.cancel()
    task_store[task_id].status = "cancelled"
    return {"status": "cancelled", "task_id": task_id}
