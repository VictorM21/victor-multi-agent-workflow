"""
Pydantic models for request/response schemas.
"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ─── Request Models ────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task: str = Field(..., description="The complex task for the multi-agent system to solve", min_length=10)
    require_approval: bool = Field(default=False, description="Pause for human approval after each worker step")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Optional metadata to attach to the task")


class CheckpointEditRequest(BaseModel):
    edited_output: str = Field(..., description="Edited version of the worker output")


# ─── Response Models ───────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str = "Task submitted for processing"


class WorkerResult(BaseModel):
    worker_name: str
    task: str
    output: str
    tool_calls: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskStatus(BaseModel):
    task_id: str
    status: str  # queued | running | completed | failed | cancelled
    task: str
    result: Optional[str] = None
    error: Optional[str] = None
    partial_results: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CheckpointStatus(BaseModel):
    checkpoint_id: str
    worker_name: str
    output: str
    status: str  # pending | approved | edited | timeout
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
