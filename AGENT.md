# System Agent for Lab 6 - Task 3

## Overview

This agent extends the Documentation Agent from Task 2 with a **`query_api` tool** that enables interaction with the deployed backend API. The agent can now query the Learning Management Service (LMS) API to retrieve system data, analytics scores, and other information.

## LLM Provider and Model

- **Provider:** OpenRouter API or Dashscope (Alibaba Cloud)
- **API Base:** Configurable via environment variables
- **Model:** Configurable via `LLM_MODEL` environment variable

The agent uses the OpenAI-compatible chat completions API with function calling support.

## Available Tools

The agent has access to three tools:

### 1. `read_file`

Reads the contents of a file from the project repository.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `path` | string | Relative path from project root (e.g., `wiki/git-workflow.md`) |

**Returns:**
```json
{
  "success": true,
  "content": "File contents here..."
}
```

### 2. `list_files`

Lists files and directories at a given path within the project.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `path` | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:**
```json
{
  "success": true,
  "files": [
    {"name": "git.md", "type": "file"},
    {"name": "git-workflow.md", "type": "file"}
  ]
}
```

### 3. `query_api` (NEW in Task 3)

Calls the deployed backend API to get system data. This tool enables the agent to answer data-dependent questions like "How many items are in the database?" or "What is the completion rate for lab-99?"

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `method` | string | HTTP method: GET, POST, PUT, or DELETE |
| `path` | string | API endpoint path (e.g., `/items/`, `/analytics/scores?lab=lab-04`) |
| `body` | string (optional) | JSON request body for POST/PUT requests |
| `authenticate` | boolean (optional) | Whether to include authentication header (default: true) |

**Returns:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {...}
}
```

**Example usage:**
```python
query_api({
    "method": "GET",
    "path": "/items/"
})
```

**Authentication:** All API requests include the `LMS_API_KEY` from `.env.docker.secret` in the `Authorization: Bearer` header. This key is automatically loaded by the `load_config()` function and passed to the `query_api` tool.

### Security: Path Validation

The `read_file` and `list_files` tools implement **directory traversal prevention**:

- ❌ Rejects paths containing `..` (e.g., `../secret.txt`)
- ❌ Rejects absolute paths (e.g., `/etc/passwd`)
- ❌ Rejects Windows-style paths (e.g., `C:\Windows\system32`)
- ✅ Only allows relative paths within the project root

## Agentic Loop Architecture

The agent implements an **agentic loop** that allows iterative tool usage:

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENTIC LOOP                             │
│                                                             │
│  1. Send question + tools ──▶ 2. Parse response            │
│         ▲                           │                       │
│         │                           ▼                       │
│         │                    Has tool_calls?               │
│         │                   ╱              ╲                │
│         │                 YES              NO               │
│         │                  │                │               │
│         │                  ▼                ▼               │
│         │           3. Execute tools   4. Return answer     │
│         │           4. Append results                        │
│         │           5. Loop to step 1                        │
│         └─────────────────────────────────────────┘         │
│                                                             │
│  Max 10 tool calls per question                             │
└─────────────────────────────────────────────────────────────┘
```

### Step-by-Step Process

1. **Send Question + Tool Definitions**
   - Build messages array with system prompt and user question
   - Include tool definitions in the API call
   - Send to LLM via OpenAI-compatible API

2. **Parse Response**
   - Check if response contains `tool_calls`
   - Check if response contains text `content`

3. **Execute Tools** (if `tool_calls` present)
   - For each tool call:
     - Extract tool name and arguments
     - Execute the corresponding function (`read_file`, `list_files`, or `query_api`)
     - Capture result or error
   - Append tool results as `tool` role messages to conversation history
   - Increment tool call counter

4. **Return Final Answer** (if text `content` present)
   - Extract text content from LLM response
   - Parse source reference from answer (wiki file path)
   - Build output JSON

5. **Loop Back** (if tools were executed)
   - Send updated message history back to LLM
   - LLM can now respond with final answer or more tool calls
   - Continue until LLM responds with text or max calls reached

### Max Tool Calls Limit

- **Maximum:** 10 tool calls per question
- **Purpose:** Prevents infinite loops and excessive API usage
- **Behavior:** Returns partial results if limit is reached

## System Prompt Strategy

The system prompt guides the LLM to effectively use tools:

```
You are a System Agent that helps users find information from both the project wiki and the deployed backend API.

You have access to three tools:
- read_file: Read the contents of a file from the project repository (e.g., wiki/git-workflow.md)
- list_files: List files and directories at a given path (e.g., wiki)
- query_api: Call the deployed backend API to get system data (items, analytics, scores, learners, interactions)

When answering questions:
1. For wiki/documentation questions (git, docker, ssh, vm, etc.) - use read_file with the expected path
2. For system data/analytics/items/scores/learners - use query_api with GET method
3. For "how many" questions about data - use query_api and count the results
4. Provide clear, direct answers based on retrieved data
5. Cite sources: wiki/<file>.md#section for docs, API endpoint for data
```

### Tool Selection Strategy

| Question Type | Tool | Example |
|--------------|------|---------|
| Documentation (git, docker, ssh) | `read_file` | "How do I resolve merge conflicts?" |
| Explore wiki structure | `list_files` | "What files are in the wiki?" |
| System data, items | `query_api` (GET) | "How many items are in the database?" |
| Analytics scores | `query_api` (GET) | "Get scores for lab-04" |
| API debugging | `query_api` (any) | "Test the /items/ endpoint" |

## Environment Variables

The agent reads all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (default: `http://localhost:42002`) | Optional |

**Important:** The autochecker runs your agent with different LLM credentials and a different backend URL. Never hardcode these values.

## Setup Instructions

### 1. Create Environment Files

```bash
cp .env.agent.example .env.agent.secret
cp .env.docker.example .env.docker.secret
```

### 2. Configure LLM Credentials

Edit `.env.agent.secret`:

```env
LLM_API_KEY=sk-or-v1-...  # Get from https://openrouter.ai/keys
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
AGENT_API_BASE_URL=http://localhost:42002
```

### 3. Configure Backend Credentials

Edit `.env.docker.secret`:

```env
LMS_API_KEY=2e5a479aaf7a0502b9a645ae8aba39fd3d2f74dfb5dedf59f9415ccc25f158bc
```

### 4. Install Dependencies

```bash
uv add requests python-dotenv
```

## Usage

Run the agent with a question:

```bash
uv run agent.py "How many items are in the database?"
```

### Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {
        "method": "GET",
        "path": "/items/"
      },
      "result": {
        "success": true,
        "status_code": 200,
        "data": {"count": 120, "items": [...]}
      }
    }
  ]
}
```

## Lessons Learned from Benchmark

### Challenge 1: Rate Limiting

Free LLM models have strict rate limits. Solution:
- Implemented exponential backoff retry logic (5s, 10s, 20s, 40s delays)
- Reduced MAX_TOOL_CALLS from 20 to 10 to minimize API calls
- Optimized system prompt to encourage direct tool usage

### Challenge 2: Tool Selection

LLM sometimes chose wrong tool. Solution:
- Made system prompt more explicit about when to use each tool
- Added examples in prompt (e.g., "wiki/git-workflow.md")
- Specified that "how many" questions should use `query_api`

### Challenge 3: Authentication

Initially forgot to pass LMS_API_KEY. Solution:
- Added `lms_api_key` to config loaded from `.env.docker.secret`
- Pass config to `query_api` function
- Use Bearer token authentication in HTTP headers

### Challenge 4: Null Content Handling

LLM returns `content: null` when making tool calls. Solution:
- Changed `msg.get("content", "")` to `(msg.get("content") or "")`
- This handles the case where content is present but null

## Testing

Run tests with pytest:

```bash
uv run pytest tests/test_agent.py -v
```

### Test Coverage

1. **Regression Tests:**
   - Merge conflicts question → expects `read_file`
   - Wiki files question → expects `list_files`
   - Items count question → expects `query_api`

2. **Unit Tests:**
   - Tool execution functions
   - Path validation (directory traversal prevention)
   - Configuration loading

3. **Integration Tests:**
   - Full agent execution
   - JSON output structure
   - Error handling

## File Structure

```
se-toolkit-lab-6/
├── agent.py              # Main agent script with tools
├── AGENT.md              # This documentation
├── .env.agent.secret     # LLM credentials (gitignored)
├── .env.docker.secret    # Backend credentials (gitignored)
├── plans/
│   └── task-3.md         # Implementation plan
└── tests/
    └── test_agent.py     # Pytest tests
```

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/items/` | List all items |
| GET | `/items/{id}/` | Get specific item |
| POST | `/items/` | Create new item |
| PUT | `/items/{id}/` | Update item |
| DELETE | `/items/{id}/` | Delete item |
| GET | `/analytics/scores` | Get analytics scores |
| GET | `/analytics/scores?lab=lab-04` | Get scores for specific lab |
| GET | `/analytics/completion-rate` | Get completion rate |
| GET | `/interactions/` | List interactions |
| GET | `/learners/` | List learners |

## Error Handling

### HTTP Errors

| Status Code | Handling |
|-------------|----------|
| 200-299 | Success - return parsed data |
| 400 | Bad Request - return error message |
| 401 | Unauthorized - check LMS_API_KEY |
| 404 | Not Found - endpoint doesn't exist |
| 429 | Rate Limit - retry with backoff |
| 500 | Server Error - backend issue |

### Connection Errors

- **Timeout:** Request timed out after 180 seconds
- **Connection Error:** Backend not running at configured URL
- **Invalid JSON:** Malformed request body

## Comparison with Task 2

| Feature | Task 2 | Task 3 |
|---------|--------|--------|
| Tools | `read_file`, `list_files` | + `query_api` |
| Source | Wiki only | Wiki + Backend API |
| Authentication | None | LMS_API_KEY for query_api |
| Data questions | ❌ No | ✅ Yes |
| Environment config | LLM only | LLM + Backend |
