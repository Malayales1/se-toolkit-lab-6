# Task 4: Containerize and Document - Implementation Plan

## Overview

This task containerizes the agent (bot) to run alongside the backend as a Docker service, and documents the deployment process in README.

## Current State

- ✅ Backend is containerized with Dockerfile and docker-compose.yml
- ✅ Agent (agent.py) works as CLI tool
- ❌ Agent is not containerized
- ❌ No deployment documentation in README

## Implementation Plan

### 1. Dockerfile for Agent (`bot/Dockerfile`)

Create a new Dockerfile following the same pattern as the backend Dockerfile:

- Use multi-stage build with `uv` for dependency management
- Use university Docker proxy for images
- Install dependencies with `uv sync --locked --no-install-project`
- Copy agent.py and run it
- Use non-root user for security

**Key considerations:**
- Use `pyproject.toml` and `uv.lock` (NOT requirements.txt)
- Agent needs both `.env.agent.secret` (LLM) and `.env.docker.secret` (LMS API) credentials
- Agent runs as CLI, not a server - may need to adapt for Docker

### 2. Add Bot Service to `docker-compose.yml`

Add a new `bot` service:

- Build from `bot/Dockerfile`
- Environment variables from `.env.docker.secret`
- Depends on `app` service (backend)
- Use Docker network: `http://app:8000` instead of `localhost:42002`
- Restart policy: `unless-stopped`

**Key considerations:**
- `AGENT_API_BASE_URL` should be `http://app:8000` inside Docker
- `LMS_API_KEY` must be passed from `.env.docker.secret`
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from `.env.agent.secret`

### 3. Add Deploy Section to README

Add a new section documenting:

- Prerequisites (environment files)
- Build and run commands
- Health check commands
- Troubleshooting guide

### 4. Git Workflow

Follow the required git workflow:

1. Create issue #4 for Task 4
2. Create branch `task/4-containerize`
3. Create PR with "Closes #4"
4. Get partner approval
5. Merge to main

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-4.md` | Create | This plan |
| `bot/Dockerfile` | Create | Docker image for agent |
| `bot/pyproject.toml` | Create | Dependencies for agent (if needed) |
| `docker-compose.yml` | Modify | Add bot service |
| `README.md` | Modify | Add Deploy section |

## Environment Variables

The bot service needs:

| Variable | Source | Purpose |
|----------|--------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint |
| `LLM_MODEL` | `.env.agent.secret` | Model name |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication |
| `AGENT_API_BASE_URL` | Runtime | Backend URL (http://app:8000 in Docker) |

## Testing Strategy

1. **Build test:** `docker compose build bot`
2. **Run test:** `docker compose up bot -d`
3. **Logs test:** `docker compose logs bot --tail 20`
4. **Integration test:** Run agent CLI command through Docker

## Acceptance Criteria

- [ ] `bot/Dockerfile` exists and builds successfully
- [ ] `docker-compose.yml` has `bot` service
- [ ] Bot container starts without errors
- [ ] README has "Deploy" section
- [ ] Git workflow followed (issue, branch, PR, approval, merge)
