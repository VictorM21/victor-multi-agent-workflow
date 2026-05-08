"""
Unit and integration tests for multi-agent workflow.
Run: pytest tests/ -v --cov=app
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import anthropic

from app.worker import WorkerAgent
from app.supervisor import SupervisorAgent
from app.checkpoint import CheckpointManager
from app.models import TaskStatus, WorkerResult


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_anthropic_client():
    """Returns a mock Anthropic client that returns a canned response."""
    client = MagicMock(spec=anthropic.Anthropic)
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(text="Mock agent response.")]
    client.messages.create.return_value = mock_response
    return client


@pytest.fixture
def task_store():
    return {}


# ─── WorkerAgent Tests ────────────────────────────────────────────────────────

class TestWorkerAgent:
    def test_unknown_worker_type_raises(self, mock_anthropic_client):
        with pytest.raises(ValueError, match="Unknown worker type"):
            WorkerAgent("invalid_type", mock_anthropic_client)

    def test_valid_worker_types_initialise(self, mock_anthropic_client):
        for wtype in ("research", "analyst", "writer"):
            agent = WorkerAgent(wtype, mock_anthropic_client)
            assert agent.worker_type == wtype

    @pytest.mark.asyncio
    async def test_execute_returns_worker_result(self, mock_anthropic_client):
        agent = WorkerAgent("writer", mock_anthropic_client)
        result = await agent.execute("Summarise: The sky is blue.")
        assert isinstance(result, WorkerResult)
        assert result.worker_name == "writer"
        assert result.output == "Mock agent response."

    @pytest.mark.asyncio
    async def test_calculate_tool_basic(self, mock_anthropic_client):
        agent = WorkerAgent("analyst", mock_anthropic_client)
        assert agent._calculate("2 + 2") == "4"
        assert agent._calculate("10 * 5") == "50"

    @pytest.mark.asyncio
    async def test_calculate_tool_rejects_invalid_chars(self, mock_anthropic_client):
        agent = WorkerAgent("analyst", mock_anthropic_client)
        result = agent._calculate("__import__('os').system('ls')")
        assert "invalid" in result.lower()

    def test_compare_items_generates_markdown_table(self, mock_anthropic_client):
        agent = WorkerAgent("analyst", mock_anthropic_client)
        table = agent._compare_items(["LangChain", "LlamaIndex"], ["Stars", "License"])
        assert "LangChain" in table
        assert "LlamaIndex" in table
        assert "Stars" in table
        assert "|" in table


# ─── CheckpointManager Tests ──────────────────────────────────────────────────

class TestCheckpointManager:
    @pytest.mark.asyncio
    async def test_create_returns_id(self):
        cm = CheckpointManager()
        cp_id = await cm.create("research", "some output", timeout=5)
        assert isinstance(cp_id, str)
        assert len(cp_id) > 0

    @pytest.mark.asyncio
    async def test_approve_unblocks_wait(self):
        cm = CheckpointManager()
        cp_id = await cm.create("analyst", "calculated result", timeout=5)

        async def do_approve():
            await asyncio.sleep(0.1)
            await cm.approve(cp_id)

        asyncio.create_task(do_approve())
        result = await cm.wait(cp_id)
        assert result == "calculated result"

    @pytest.mark.asyncio
    async def test_edit_replaces_output(self):
        cm = CheckpointManager()
        cp_id = await cm.create("writer", "original output", timeout=5)

        async def do_edit():
            await asyncio.sleep(0.1)
            await cm.edit(cp_id, "edited output")

        asyncio.create_task(do_edit())
        result = await cm.wait(cp_id)
        assert result == "edited output"

    @pytest.mark.asyncio
    async def test_timeout_returns_original_output(self):
        cm = CheckpointManager()
        cp_id = await cm.create("writer", "original", timeout=1)  # 1 second timeout
        result = await cm.wait(cp_id)
        assert result == "original"

    @pytest.mark.asyncio
    async def test_get_pending_returns_unresolved(self):
        cm = CheckpointManager()
        await cm.create("research", "output A", timeout=60)
        await cm.create("analyst", "output B", timeout=60)
        pending = cm.get_pending()
        assert len(pending) == 2


# ─── SupervisorAgent Tests ────────────────────────────────────────────────────

class TestSupervisorAgent:
    def test_supervisor_initialises(self, mock_anthropic_client, task_store):
        task_id = "test-task-id"
        task_store[task_id] = TaskStatus(task_id=task_id, status="queued", task="test task")
        
        with patch("app.supervisor.anthropic.Anthropic", return_value=mock_anthropic_client):
            supervisor = SupervisorAgent(
                task_id=task_id,
                task_store=task_store,
                require_approval=False,
            )
        assert supervisor.task_id == task_id
        assert len(supervisor.workers) == 3

    @pytest.mark.asyncio
    async def test_run_completes_task(self, mock_anthropic_client, task_store):
        task_id = "test-run-id"
        task_store[task_id] = TaskStatus(task_id=task_id, status="queued", task="research AI trends")

        # Mock supervisor decompose returning a single-worker plan
        plan_response = MagicMock()
        plan_response.stop_reason = "end_turn"
        plan_response.content = [MagicMock(text=json.dumps({
            "subtasks": [{"worker": "writer_worker", "task": "Write a summary about AI trends"}]
        }))]

        synthesis_response = MagicMock()
        synthesis_response.stop_reason = "end_turn"
        synthesis_response.content = [MagicMock(text="Final synthesised answer about AI trends.")]

        worker_response = MagicMock()
        worker_response.stop_reason = "end_turn"
        worker_response.content = [MagicMock(text="Worker output about AI trends.")]

        mock_anthropic_client.messages.create.side_effect = [
            plan_response,
            worker_response,
            synthesis_response,
        ]

        with patch("app.supervisor.anthropic.Anthropic", return_value=mock_anthropic_client):
            supervisor = SupervisorAgent(
                task_id=task_id,
                task_store=task_store,
                require_approval=False,
            )
            supervisor.workers["writer_worker"].client = mock_anthropic_client

        await supervisor.run("research AI trends")

        assert task_store[task_id].status == "completed"
        assert "Final synthesised" in task_store[task_id].result
