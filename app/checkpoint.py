"""
Human-in-the-Loop Checkpoint Manager.
Pauses agent execution and waits for human approval/edit before continuing.
"""
import asyncio
import uuid
from typing import Optional
import structlog

logger = structlog.get_logger()


class CheckpointManager:
    """
    Manages human-in-the-loop checkpoints.

    Flow:
      1. Supervisor calls create() — stores worker output and returns checkpoint_id
      2. FastAPI endpoint returns checkpoint_id to user (via SSE stream or polling)
      3. User calls POST /checkpoint/{id}/approve or /checkpoint/{id}/edit
      4. Supervisor is unblocked and continues with (possibly edited) output
    """

    def __init__(self):
        self._checkpoints: dict[str, dict] = {}
        self._futures: dict[str, asyncio.Future] = {}

    async def create(
        self,
        worker_name: str,
        output: str,
        timeout: int = 300,
    ) -> str:
        """Create a new checkpoint and return its ID."""
        checkpoint_id = str(uuid.uuid4())[:8]
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        self._checkpoints[checkpoint_id] = {
            "checkpoint_id": checkpoint_id,
            "worker_name": worker_name,
            "output": output,
            "status": "pending",
            "timeout": timeout,
        }
        self._futures[checkpoint_id] = future

        logger.info(
            "Checkpoint created",
            checkpoint_id=checkpoint_id,
            worker=worker_name,
            timeout=timeout,
        )
        return checkpoint_id

    async def wait(self, checkpoint_id: str) -> str:
        """
        Block until the checkpoint is resolved (approved/edited) or times out.
        Returns the (possibly edited) output string.
        """
        cp = self._checkpoints.get(checkpoint_id)
        future = self._futures.get(checkpoint_id)

        if not cp or not future:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        timeout = cp.get("timeout", 300)
        try:
            result = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            cp["status"] = "timeout"
            logger.warning("Checkpoint timed out", checkpoint_id=checkpoint_id)
            # On timeout, continue with original output
            return cp["output"]

    async def approve(self, checkpoint_id: str) -> bool:
        """Approve worker output as-is and unblock the supervisor."""
        cp = self._checkpoints.get(checkpoint_id)
        future = self._futures.get(checkpoint_id)

        if not cp or not future or future.done():
            return False

        cp["status"] = "approved"
        future.set_result(cp["output"])
        logger.info("Checkpoint approved", checkpoint_id=checkpoint_id)
        return True

    async def edit(self, checkpoint_id: str, edited_output: str) -> bool:
        """Edit worker output, then unblock the supervisor with the new output."""
        cp = self._checkpoints.get(checkpoint_id)
        future = self._futures.get(checkpoint_id)

        if not cp or not future or future.done():
            return False

        cp["status"] = "edited"
        cp["output"] = edited_output
        future.set_result(edited_output)
        logger.info(
            "Checkpoint edited",
            checkpoint_id=checkpoint_id,
            new_length=len(edited_output),
        )
        return True

    def get_pending(self) -> list[dict]:
        """Return all checkpoints awaiting human input."""
        return [
            cp for cp in self._checkpoints.values()
            if cp["status"] == "pending"
        ]
