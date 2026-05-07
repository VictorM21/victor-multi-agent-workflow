# victor-multi-agent-workflow

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude_3.5-orange?logo=anthropic)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

> **Production-grade multi-agent AI system** -- supervisor orchestrates specialist worker agents using Anthropic Claude with tool use, human-in-the-loop checkpoints, and a FastAPI REST interface.

---

## Architecture

The system uses a hierarchical Supervisor/Worker pattern:

- **Supervisor Agent** (Claude claude-3-5-sonnet): Receives complex tasks, decomposes them, routes sub-tasks to specialist workers, and synthesizes final results
- **Research Worker**: Web search + URL fetch tools
- **Analyst Worker**: Calculator + data comparison tools
- **Writer Worker**: Summarization + draft generation tools
- **Human Checkpoint Layer**: Configurable pause points for review/approval before continuing

---

## Features

| Feature | Detail |
|---------|--------|
| **Supervisor/Worker Pattern** | Hierarchical agent orchestration with role separation |
| **Tool Use** | Web search, URL fetch, calculator, data compare, text summarize |
| **Human-in-the-Loop** | Configurable pause points -- approve, edit, or reject worker output |
| **Streaming** | SSE streaming of agent reasoning steps |
| **Retry & Fallback** | Exponential backoff on tool failures, fallback to next worker |
| **Observability** | Structured logging of all agent decisions and tool calls |
| **REST API** | FastAPI with OpenAPI docs, async handlers, Pydantic validation |
| **Docker** | Multi-stage build, non-root user, healthcheck |

---

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/VictorM21/victor-multi-agent-workflow.git
cd victor-multi-agent-workflow

# 2. Configure environment
cp .env.example .env
# Edit .env -- add ANTHROPIC_API_KEY

# 3. Run with Docker
docker compose up --build

# 4. Try it
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Research the top 3 open-source LLM frameworks and compare their GitHub stars, license, and production readiness"}'
```

API docs available at **http://localhost:8000/docs**

---

## Project Structure

```
victor-multi-agent-workflow/
├── app/
│   ├── main.py                 # FastAPI app + routes
│   ├── supervisor.py           # Supervisor agent + orchestration logic
│   ├── worker.py               # Worker agent base class
│   ├── workers/
│   │   ├── research_worker.py  # Web search + URL fetch tools
│   │   ├── analyst_worker.py   # Calculator + comparison tools
│   │   └── writer_worker.py    # Summarization + draft tools
│   ├── tools/
│   │   ├── definitions.py      # Anthropic tool schemas (JSON)
│   │   └── executors.py        # Tool execution handlers
│   ├── checkpoint.py           # Human-in-the-loop checkpoint logic
│   ├── config.py               # Pydantic Settings
│   └── models.py               # Pydantic request/response models
├── tests/
│   ├── test_supervisor.py      # Unit tests for orchestration
│   ├── test_workers.py         # Worker + tool tests
│   └── test_api.py             # FastAPI endpoint tests
├── notebooks/
│   └── 02_multi_agent_exploration.ipynb
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /task | Submit a complex task for multi-agent processing |
| GET | /task/{task_id} | Poll task status and partial results |
| GET | /task/{task_id}/stream | SSE stream of agent reasoning steps |
| POST | /checkpoint/{id}/approve | Approve worker output and continue |
| POST | /checkpoint/{id}/edit | Edit worker output before continuing |
| DELETE | /task/{task_id} | Cancel a running task |
| GET | /health | Health check |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude claude-3-5-sonnet-20241022 |
| Framework | FastAPI 0.111 + Pydantic v2 |
| Async | Python asyncio + httpx |
| Streaming | Server-Sent Events (SSE) |
| Storage | Redis (task state) + SQLite (audit log) |
| Container | Docker + docker-compose |
| Testing | pytest + pytest-asyncio + respx |
| Observability | structlog + OpenTelemetry |

---

## Example Use Cases

- **Research Synthesis** -- Compare LLM frameworks and write a decision matrix
- **Data Analysis Pipeline** -- Fetch a dataset URL, calculate stats, identify outliers, write findings
- **Competitive Analysis** -- Research top 5 competitors, extract pricing, summarize positioning
- **Content Generation** -- Research a topic, fact-check claims, write a 500-word blog post

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| ANTHROPIC_API_KEY | Yes | Your Anthropic API key |
| SUPERVISOR_MODEL | Optional | Claude model for supervisor (default: claude-3-5-sonnet-20241022) |
| WORKER_MODEL | Optional | Claude model for workers (default: claude-3-haiku-20240307) |
| MAX_WORKERS | Optional | Max concurrent workers (default: 3) |
| CHECKPOINT_TIMEOUT | Optional | Seconds to wait for human approval (default: 300) |
| REDIS_URL | Optional | Redis connection string (default: redis://localhost:6379) |
| LOG_LEVEL | Optional | Logging level (default: INFO) |

---

## What I Learned Building This

- **Hierarchical agent orchestration** separating planning from execution dramatically improves reliability
- **Tool schemas** in the Anthropic API require precise JSON -- invalid schemas silently cause agent confusion
- **Human-in-the-loop checkpoints** are essential: agents make plausible but wrong decisions ~15% of the time
- **Streaming agent reasoning** via SSE lets you catch problems before final output
- **Redis for task state** beats in-memory dict for restartability and horizontal scaling

---

## Related Projects

- [victor-rag-document-qa](https://github.com/VictorM21/victor-rag-document-qa) -- Production RAG pipeline
- [victor-analytics-portfolio](https://github.com/VictorM21/victor-analytics-portfolio) -- Data analytics projects

---

*Part of my AI Engineering portfolio -- building production-grade AI systems.*
