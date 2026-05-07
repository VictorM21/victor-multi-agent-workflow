"""
Supervisor Agent - orchestrates worker agents to complete complex tasks.
Uses Anthropic Claude claude-3-5-sonnet as the planning/synthesis model.
"""
import json
import asyncio
from typing import Optional, AsyncIterator
import anthropic
import structlog

from app.config import settings
from app.models import TaskStatus, WorkerResult
from app.worker import WorkerAgent
from app.checkpoint import CheckpointManager

logger = structlog.get_logger()

SUPERVISOR_SYSTEM_PROMPT = """You are a Supervisor AI agent. Your job is to:
1. Analyze the user's complex task
2. Decompose it into sub-tasks for specialist worker agents
3. Route each sub-task to the appropriate worker (research, analyst, or writer)
4. Collect and synthesize worker results into a final comprehensive response

Available workers:
- research_worker: Web search, URL fetching, fact-finding
- analyst_worker: Data calculation, comparison, structured analysis  
- writer_worker: Summarization, draft generation, formatting

Always respond with a JSON plan like:
{
  "subtasks": [
    {"worker": "research_worker", "task": "specific research task"},
    {"worker": "analyst_worker", "task": "analysis based on research"},
    {"worker": "writer_worker", "task": "write final synthesis"}
  ]
}
"""


class SupervisorAgent:
    def __init__(
        self,
        task_id: str,
        task_store: dict,
        require_approval: bool = False,
    ):
        self.task_id = task_id
        self.task_store = task_store
        self.require_approval = require_approval
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.checkpoint_manager = CheckpointManager()
        self._events: list[str] = []
        self._cancelled = False
        self.workers = {
            "research_worker": WorkerAgent("research", self.client),
            "analyst_worker": WorkerAgent("analyst", self.client),
            "writer_worker": WorkerAgent("writer", self.client),
        }

    async def run(self, task: str) -> None:
        """Main orchestration loop."""
        status = self.task_store[self.task_id]
        status.status = "running"

        try:
            self._emit(f"Supervisor analyzing task: {task[:100]}...")
            plan = await self._decompose_task(task)
            self._emit(f"Plan created: {len(plan['subtasks'])} sub-tasks")

            worker_results: list[WorkerResult] = []
            for i, subtask in enumerate(plan["subtasks"]):
                if self._cancelled:
                    status.status = "cancelled"
                    return

                worker_name = subtask["worker"]
                worker_task = subtask["task"]
                self._emit(f"Step {i+1}/{len(plan['subtasks'])}: {worker_name} -> {worker_task[:80]}")

                result = await self.workers[worker_name].execute(worker_task)
                
                if self.require_approval:
                    result = await self._await_checkpoint(worker_name, result)

                worker_results.append(result)
                status.partial_results.append(result.dict())

            self._emit("Synthesizing final response...")
            final_output = await self._synthesize(task, worker_results)
            status.status = "completed"
            status.result = final_output
            self._emit("Task completed successfully")

        except Exception as e:
            logger.exception("Supervisor error", task_id=self.task_id, error=str(e))
            status.status = "failed"
            status.error = str(e)

    async def _decompose_task(self, task: str) -> dict:
        """Ask the supervisor model to create a plan."""
        message = self.client.messages.create(
            model=settings.supervisor_model,
            max_tokens=1024,
            system=SUPERVISOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Create a plan to: {task}"}],
        )
        text = message.content[0].text
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])

    async def _synthesize(self, original_task: str, results: list[WorkerResult]) -> str:
        """Synthesize all worker results into a final response."""
        results_text = "\n\n".join(
            f"=== {r.worker_name} ===\n{r.output}" for r in results
        )
        message = self.client.messages.create(
            model=settings.supervisor_model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"Original task: {original_task}\n\nWorker results:\n{results_text}\n\nSynthesize a comprehensive final response."
            }],
        )
        return message.content[0].text

    async def _await_checkpoint(self, worker_name: str, result: WorkerResult) -> WorkerResult:
        """Pause for human approval before continuing."""
        checkpoint_id = await self.checkpoint_manager.create(
            worker_name=worker_name,
            output=result.output,
            timeout=settings.checkpoint_timeout,
        )
        self._emit(f"CHECKPOINT: Review {worker_name} output (id: {checkpoint_id})")
        approved_output = await self.checkpoint_manager.wait(checkpoint_id)
        result.output = approved_output
        return result

    def _emit(self, event: str) -> None:
        """Add event to stream."""
        import json
        self._events.append(json.dumps({"event": event, "task_id": self.task_id}))

    async def event_stream(self) -> AsyncIterator[str]:
        """Yield events as they occur."""
        sent = 0
        while True:
            while sent < len(self._events):
                yield self._events[sent]
                sent += 1
            status = self.task_store.get(self.task_id)
            if status and status.status in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(0.1)

    async def approve_checkpoint(self, checkpoint_id: str) -> bool:
        return await self.checkpoint_manager.approve(checkpoint_id)

    async def edit_checkpoint(self, checkpoint_id: str, edited_output: str) -> bool:
        return await self.checkpoint_manager.edit(checkpoint_id, edited_output)

    async def cancel(self) -> None:
        self._cancelled = True
