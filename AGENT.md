# System Agent for Lab 6 - Task 3

## Overview

This agent extends the Documentation Agent from Task 2 with a **`query_api` tool** that enables interaction with the deployed backend API. The agent can now query the Learning Management Service (LMS) API to retrieve system data, analytics scores, and other information.

## LLM Provider and Model

- **Provider:** OpenRouter API
- **Model:** `nvidia/nemotron-3-super-120b-a12b:free` (free, no credits required)
- **API Base:** `https://openrouter.ai/api/v1`

**Alternative free models:**
- `meta-llama/llama-3.3-70b-instruct:free` - Best overall
- `mistralai/devstral-2512:free` - Best for coding
- `google/gemma-3-12b-it:free` - Good for general tasks

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

Or on error:
```json
{
  "success": false,
  "error": "Error message"
}
```

**Example usage:**
```python
read_file({"path": "wiki/git-workflow.md"})
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
    {"name": "git-workflow.md", "type": "file"},
    {"name": "images", "type": "dir"}
  ]
}
```

Or on error:
```json
{
  "success": false,
  "error": "Error message"
}
```

**Example usage:**
```python
list_files({"path": "wiki"})
```

### 3. `query_api`

Calls the deployed backend API to get system data.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `method` | string | HTTP method: GET, POST, PUT, or DELETE |
| `path` | string | API endpoint path (e.g., `/items/`, `/analytics/scores?lab=lab-04`) |
| `body` | string (optional) | JSON request body for POST/PUT requests |

**Returns:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {...}
}
```

Or on error:
```json
{
  "success": false,
  "status_code": 404,
  "error": "Error message"
}
```

**Example usage:**
```python
query_api({
    "method": "GET",
    "path": "/items/"
})
```

**Authentication:** All API requests include the `LMS_API_KEY` from `.env.docker.secret` in the `Authorization: Bearer` header.

### Security: Path Validation

The `read_file` and `list_files` tools implement **directory traversal prevention** to ensure security:

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
     - Execute the corresponding function (`read_file` or `list_files`)
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

The system prompt guides the LLM to effectively use tools for documentation discovery:

```
You are a Documentation Agent that helps users find information in the project wiki.

You have access to two tools:
- read_file: Read the contents of a file from the project repository
- list_files: List files and directories at a given path

When answering questions:
1. Use tools to explore the wiki and find relevant documentation
2. Always cite your sources using the format: wiki/<filename>.md#<section>
3. If you're not sure where information is, use list_files to explore directories
4. Read files using read_file to get detailed information
5. Provide clear, accurate answers based on the documentation you find

Important:
- Only access files within the project repository
- Paths should be relative to the project root (e.g., 'wiki/git-workflow.md')
- Never attempt to access files outside the repository
```

### Key Strategies

1. **Tool-first approach:** LLM is instructed to use tools before answering
2. **Source citation:** Answers must include wiki file references
3. **Exploratory behavior:** Use `list_files` when uncertain about file locations
4. **Security boundaries:** Clear instructions to stay within project root

## Setup Instructions

### 1. Create Environment File

```bash
cp .env.agent.example .env.agent.secret
```

### 2. Configure Credentials

Edit `.env.agent.secret` with your OpenRouter API credentials:

```env
LLM_API_KEY=sk-or-v1-...  # Get from https://openrouter.ai/keys
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=alibaba/qwen3-coder-plus
```

**To get your API key:**
1. Go to [OpenRouter](https://openrouter.ai/)
2. Sign in with your GitHub/Google account
3. Navigate to **Keys** section
4. Create a new API key
5. Copy the key (starts with `sk-or-v1-`)

### 3. Install Dependencies

```bash
uv add openai python-dotenv
```

## Usage

Run the agent with a question:

```bash
uv run agent.py "How do I resolve merge conflicts?"
```

### Output Format

The agent outputs valid JSON to stdout:

```json
{
  "answer": "To resolve merge conflicts, follow these steps:\n1. Identify the conflicting files...\n2. Open the files and locate conflict markers...\n3. Edit the files to resolve conflicts...\n4. Stage the resolved files...\n5. Complete the merge...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {
        "path": "wiki/git-workflow.md"
      },
      "result": {
        "success": true,
        "content": "# Git workflow for tasks\n\n## Resolving Merge Conflicts\n\nWhen Git cannot automatically merge changes..."
      }
    }
  ]
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The final answer from the LLM |
| `source` | string | Wiki section reference (e.g., `wiki/git-workflow.md#section`) |
| `tool_calls` | array | Array of all tool calls made during execution |

### Tool Call Object

Each tool call in the `tool_calls` array contains:

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Name of the tool used (`read_file` or `list_files`) |
| `args` | object | Arguments passed to the tool |
| `result` | object | Result returned by the tool execution |

## Examples

### Example 1: Question about Merge Conflicts

**Input:**
```bash
uv run agent.py "How do I resolve merge conflicts in Git?"
```

**Expected behavior:**
- LLM calls `read_file` with path `wiki/git-workflow.md`
- LLM reads the merge conflict resolution section
- LLM provides answer with source citation

**Expected output:**
```json
{
  "answer": "To resolve merge conflicts...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": {"success": true, "content": "..."}
    }
  ]
}
```

### Example 2: Exploring Wiki Structure

**Input:**
```bash
uv run agent.py "What files are in the wiki directory?"
```

**Expected behavior:**
- LLM calls `list_files` with path `wiki`
- LLM receives list of files and directories
- LLM summarizes the wiki structure

**Expected output:**
```json
{
  "answer": "The wiki directory contains the following files: git.md, git-workflow.md, docker.md, api.md, and several others...",
  "source": "",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": {
        "success": true,
        "files": [
          {"name": "git.md", "type": "file"},
          {"name": "git-workflow.md", "type": "file"}
        ]
      }
    }
  ]
}
```

### Example 3: Multi-step Tool Usage

**Input:**
```bash
uv run agent.py "What Docker commands are available and how do I use them?"
```

**Expected behavior:**
1. LLM calls `list_files` to find Docker-related files
2. LLM calls `read_file` on `wiki/docker.md`
3. LLM may call `read_file` on `wiki/docker-compose.md`
4. LLM synthesizes answer from multiple sources

**Expected output:**
```json
{
  "answer": "Docker commands include: docker build, docker run, docker ps, docker stop...\nFor multi-container setups, use docker-compose...",
  "source": "wiki/docker.md",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": {...}},
    {"tool": "read_file", "args": {"path": "wiki/docker.md"}, "result": {...}},
    {"tool": "read_file", "args": {"path": "wiki/docker-compose.md"}, "result": {...}}
  ]
}
```

## Error Handling

### Invalid Path (Directory Traversal)

```json
{
  "tool": "read_file",
  "args": {"path": "../secret.txt"},
  "result": {
    "success": false,
    "error": "Invalid path: directory traversal not allowed. Path: ../secret.txt"
  }
}
```

### File Not Found

```json
{
  "tool": "read_file",
  "args": {"path": "wiki/nonexistent.md"},
  "result": {
    "success": false,
    "error": "File not found: wiki/nonexistent.md"
  }
}
```

### Max Tool Calls Reached

```json
{
  "answer": "I reached the maximum number of tool calls. Here's what I found so far...",
  "source": "",
  "tool_calls": [...]
}
```

## Testing

Run tests with pytest:

```bash
uv run pytest tests/test_agent.py -v
```

### Test Coverage

The test suite includes:

1. **Regression Tests:**
   - Test merge conflicts question → expects `read_file` in tool_calls
   - Test wiki files question → expects `list_files` in tool_calls

2. **Unit Tests:**
   - Test tool execution functions
   - Test path validation
   - Test agentic loop with mocked LLM

3. **Integration Tests:**
   - Test full agent execution
   - Test JSON output structure
   - Test error handling

## File Structure

```
se-toolkit-lab-6/
├── agent.py              # Main agent script with tools
├── AGENT.md              # This documentation
├── .env.agent.example    # Example environment file
├── .env.agent.secret     # Actual credentials (gitignored)
├── plans/
│   └── task-2.md         # Implementation plan
└── tests/
    └── test_agent.py     # Pytest tests
```

## Comparison with Task 1

| Feature | Task 1 | Task 2 |
|---------|--------|--------|
| Tool calling | ❌ No | ✅ Yes |
| Agentic loop | ❌ No | ✅ Yes |
| File reading | ❌ No | ✅ `read_file` |
| Directory listing | ❌ No | ✅ `list_files` |
| Source citation | ❌ No | ✅ `source` field |
| Max tool calls | N/A | 10 per question |
| System prompt | ❌ No | ✅ Yes |
| Path security | N/A | ✅ Directory traversal prevention |
