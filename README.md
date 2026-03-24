# Lab 6 — Build Your Own Agent

The lab gets updated regularly, so do [sync your fork with the upstream](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork#syncing-a-fork-branch-from-the-command-line) from time to time.

<h2>Table of contents</h2>

- [Lab story](#lab-story)
- [Learning advice](#learning-advice)
- [Learning outcomes](#learning-outcomes)
- [Tasks](#tasks)
  - [Prerequisites](#prerequisites)
  - [Required](#required)
  - [Optional (recommended)](#optional-recommended)

## Lab story

> "Everybody should implement an agent loop at some point. It's the hello-world of agentic engineering."

You will build a CLI agent that can answer questions by reading the lab docs and querying the backend API. You then will evaluate the agent against a benchmark.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────┐   │
│  │  agent.py    │────▶│  OpenRouter API                  │   │
│  │  (CLI)       │◀────│  (a free LLM with tool use)      │   │
│  └──────┬───────┘     └──────────────────────────────────┘   │
│         │                                                    │
│         │ tool calls                                         │
│         ├──────────▶ read_file(path) ──▶ source code, wiki/  │
│         ├──────────▶ list_files(dir)  ──▶ files and folders  │
│         ├──────────▶ query_api(path)  ──▶ backend API        │
│         │                                                    │
│  ┌──────┴───────┐                                            │
│  │  Docker      │  app (FastAPI) ─── postgres (data)         │
│  │  Compose     │  caddy (frontend)                          │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

## Learning advice

This lab is different from previous ones. You are not following step-by-step instructions — you are building something and iterating until it works. Use your coding agent to help you understand and plan:

> Read task X. What exactly do we need to deliver? Explain, I want to understand.

> Why does an agent need a loop? Walk me through the flow.

> My agent failed this question: "...". Diagnose why and suggest a fix.

The agent you build is simple (~100-200 lines). The learning comes from debugging it against the benchmark.

## Learning outcomes

By the end of this lab, you should be able to:

- Explain how an agentic loop works: user input → LLM → tool call → execute → feed result → repeat until final answer.
- Integrate with an LLM API using the OpenAI-compatible chat completions format with tool/function calling.
- Implement tools that read files, list directories, and query HTTP APIs, then register them as function-calling schemas.
- Build a CLI that accepts structured input and produces structured output (JSON).
- Debug agent behavior by examining tool call traces, identifying prompt issues, and fixing tool implementations.
- Assess agent quality against a benchmark, iterating on prompts and tools to improve pass rate.

In simple words, you should be able to say:
>
> 1. I built an agent that calls an LLM and answers questions!
> 2. I gave it tools to read files and query my API!
> 3. I iterated until it passed the evaluation benchmark!

## Tasks

### Prerequisites

1. Complete the [lab setup](./lab/tasks/setup-simple.md#lab-setup)

> **Note**: If this is the first lab you are attempting in this course, you need to do the [full version of the setup](./lab/tasks/setup.md#lab-setup)

### Required

1. [Call an LLM from code](./lab/tasks/required/task-1.md#call-an-llm-from-code)
2. [The documentation agent](./lab/tasks/required/task-2.md#the-documentation-agent)
3. [The system agent](./lab/tasks/required/task-3.md#the-system-agent)
4. [Containerize and document](./lab/tasks/required/task-4.md#containerize-and-document)

### Optional (recommended)

1. [Advanced agent features](./lab/tasks/optional/task-1.md#advanced-agent-features)

## Deploy

This section describes how to deploy the agent and backend using Docker.

### Prerequisites

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/se-toolkit-lab-6.git
   cd se-toolkit-lab-6
   ```

2. **Create environment files:**

   **LLM credentials** (`.env.agent.secret`):
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

   Edit `.env.agent.secret`:
   ```env
   LLM_API_KEY=sk-or-v1-...  # Get from https://openrouter.ai/keys
   LLM_API_BASE=https://openrouter.ai/api/v1
   LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
   ```

   **Backend credentials** (`.env.docker.secret`):
   ```bash
   cp .env.docker.example .env.docker.secret
   ```

   Edit `.env.docker.secret`:
   ```env
   LMS_API_KEY=your-lms-api-key
   # ... other backend variables
   ```

### Build and Run

Build and start all services (backend, postgres, caddy, and bot):

```bash
docker compose --env-file .env.docker.secret up --build -d
```

Check the status of all containers:

```bash
docker compose --env-file .env.docker.secret ps
```

You should see:
- `app` - Backend FastAPI service
- `postgres` - PostgreSQL database
- `pgadmin` - Database admin UI
- `caddy` - Frontend web server
- `bot` - System agent (runs once and exits)

### Run the Bot

The bot is a CLI tool, so run it on-demand:

```bash
# Run a question through the containerized bot
docker compose --env-file .env.docker.secret run --rm bot python agent.py "How many items are in the database?"
```

### Health Checks

**Check backend health:**
```bash
curl -sf http://localhost:42002/docs
```

**Check bot logs:**
```bash
docker compose --env-file .env.docker.secret logs bot --tail 20
```

**Check all containers:**
```bash
docker compose --env-file .env.docker.secret ps
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot container exits immediately | Bot is a CLI tool - it runs once and exits. Use `docker compose run` to execute questions. |
| LLM API errors | Check `LLM_API_KEY` and `LLM_API_BASE` in `.env.agent.secret` |
| Backend connection errors | Ensure `AGENT_API_BASE_URL=http://app:8000` in docker-compose.yml |
| Port conflicts | Change host ports in `.env.docker.secret` (e.g., `APP_HOST_PORT`) |

### Stop and Cleanup

```bash
# Stop all services
docker compose --env-file .env.docker.secret down

# Stop and remove volumes (database data will be lost)
docker compose --env-file .env.docker.secret down -v
```
