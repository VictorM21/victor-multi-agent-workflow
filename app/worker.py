"""
Worker Agent - specialist AI agent that executes specific sub-tasks with tools.
Three types: research (web), analyst (math/compare), writer (synthesis).
"""
import anthropic
import httpx
import structlog

from app.config import settings
from app.models import WorkerResult

logger = structlog.get_logger()

# ─── Tool schemas ──────────────────────────────────────────────────────────────

RESEARCH_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current information on any topic.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch and return the text content of a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
]

ANALYST_TOOLS = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression and return the numeric result.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
    {
        "name": "compare_items",
        "description": "Generate a markdown comparison table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "dimensions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["items", "dimensions"],
        },
    },
]

WORKER_CONFIGS: dict[str, dict] = {
    "research": {
        "tools": RESEARCH_TOOLS,
        "system": "You are a Research Worker. Use tools to gather accurate, up-to-date information. Cite sources.",
    },
    "analyst": {
        "tools": ANALYST_TOOLS,
        "system": "You are an Analyst Worker. Use tools to compute and compare data. Be precise and structured.",
    },
    "writer": {
        "tools": [],
        "system": "You are a Writer Worker. Synthesise provided information into clear, professional content.",
    },
}


class WorkerAgent:
    """Executes a single sub-task with an agentic tool-use loop (up to 5 turns)."""

    def __init__(self, worker_type: str, client: anthropic.Anthropic) -> None:
        if worker_type not in WORKER_CONFIGS:
            raise ValueError(f"Unknown worker type '{worker_type}'. Choose from: {list(WORKER_CONFIGS)}")
        self.worker_type = worker_type
        self.client = client
        self.config = WORKER_CONFIGS[worker_type]

    async def execute(self, task: str) -> WorkerResult:
        logger.info("Worker executing", worker=self.worker_type, task=task[:80])
        messages = [{"role": "user", "content": task}]
        output = ""

        for _ in range(5):
            kwargs: dict = {
                "model": settings.worker_model,
                "max_tokens": 1024,
                "system": self.config["system"],
                "messages": messages,
            }
            if self.config["tools"]:
                kwargs["tools"] = self.config["tools"]

            response = self.client.messages.create(**kwargs)

            if response.stop_reason == "end_turn":
                output = response.content[0].text
                break
            elif response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._run_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                output = str(response.content[0])
                break

        return WorkerResult(worker_name=self.worker_type, task=task, output=output, tool_calls=[])

    async def _run_tool(self, name: str, inputs: dict) -> str:
        try:
            if name == "web_search":
                return await self._web_search(inputs["query"])
            if name == "fetch_url":
                return await self._fetch_url(inputs["url"])
            if name == "calculate":
                return self._calculate(inputs["expression"])
            if name == "compare_items":
                return self._compare_items(inputs["items"], inputs["dimensions"])
            return f"Unknown tool: {name}"
        except Exception as exc:
            logger.error("Tool failed", tool=name, error=str(exc))
            return f"Tool error: {exc}"

    async def _web_search(self, query: str) -> str:
        # Stub — replace with SerpAPI / Brave Search / Tavily
        return f"[Mock search: '{query}'] Connect a real search API for production."

    async def _fetch_url(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, follow_redirects=True)
            return r.text[:3000]

    def _calculate(self, expr: str) -> str:
        if not all(c in "0123456789+-*/()., " for c in expr):
            return "Error: invalid characters in expression"
        try:
            return str(eval(expr, {"__builtins__": {}}))
        except Exception as exc:
            return f"Calculation error: {exc}"

    def _compare_items(self, items: list, dimensions: list) -> str:
        header = "| Item | " + " | ".join(dimensions) + " |"
        sep = "|---|" + "---|" * len(dimensions)
        rows = [f"| {i} | " + " | ".join(["—"] * len(dimensions)) + " |" for i in items]
        return "\n".join([header, sep, *rows])
