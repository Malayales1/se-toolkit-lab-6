# Task 2: Documentation Agent

## Overview

This task extends the CLI agent from Task 1 with tool-calling capabilities to enable documentation discovery. The agent can now read files and list directories within the project to answer questions about the wiki documentation.

## Tool Schemas Implementation

### Tool Definitions (OpenAI Function Calling Format)

Two tools are implemented using the OpenAI-compatible function calling schema:

#### 1. `read_file` Tool

```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the project repository",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                }
            },
            "required": ["path"]
        }
    }
}
```

**Purpose:** Reads the contents of a file from the project root directory.

**Security:** Prevents directory traversal attacks by rejecting paths containing `../`.

#### 2. `list_files` Tool

```python
{
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files and directories at a given path",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path from project root (e.g., 'wiki')"
                }
            },
            "required": ["path"]
        }
    }
}
```

**Purpose:** Lists all files and directories at a specified path within the project.

**Security:** Prevents directory traversal attacks by rejecting paths containing `../`.

### Tool Implementation Details

Both tools:
- Accept relative paths from project root
- Validate paths to prevent directory traversal
- Return structured results for the LLM to process
- Handle errors gracefully (file not found, permission denied, etc.)

## Agentic Loop Architecture

### Loop Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC LOOP                                 │
│                                                                 │
│  ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐  │
│  │ 1. Send     │────▶│ 2. Parse     │────▶│ 3. Tool Calls?  │  │
│  │    question │     │    response  │     │                 │  │
│  │    + tools  │     │              │     └────────┬────────┘  │
│  └─────────────┘     └──────────────┘              │          │
│       ▲                                           │          │
│       │         ┌─────────────────────────┐       │          │
│       │         │ 4. Execute Tools        │◀──────┘          │
│       │         │    - read_file()        │                  │
│       │         │    - list_files()       │                  │
│       │         │    - Append results     │                  │
│       │         │    - Go to step 1       │                  │
│       │         └─────────────────────────┘                  │
│       │                                                      │
│       │         ┌─────────────────────────┐                  │
│       │         │ 5. Text Response        │◀─────────────────┘
│       │         │    - Final answer       │
│       │         │    - Return result      │
│       └─────────┴─────────────────────────┘
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Process

1. **Send Question + Tool Definitions**
   - Build messages array with user question
   - Include tool definitions in the API call
   - Send to LLM via OpenAI-compatible API

2. **Parse Response**
   - Check if response contains `tool_calls`
   - Check if response contains text `content`

3. **Decision Point**
   - If `tool_calls` present → Execute tools (step 4)
   - If text `content` present → Final answer (step 5)

4. **Execute Tools**
   - For each tool call:
     - Extract tool name and arguments
     - Execute the corresponding function
     - Capture result or error
   - Append tool results as `tool` role messages
   - Increment tool call counter
   - Check max tool calls limit (10)
   - Loop back to step 1

5. **Return Final Answer**
   - Extract text content from LLM response
   - Build output JSON with:
     - `answer`: The final answer
     - `source`: Wiki section reference
     - `tool_calls`: Array of all tool calls made

### Max Tool Calls Limit

- Maximum 10 tool calls per question
- Prevents infinite loops and excessive API usage
- Returns partial results if limit reached

## Path Security Strategy

### Directory Traversal Prevention

To prevent security vulnerabilities from path traversal attacks (`../`), the following validation is implemented:

```python
def is_safe_path(path: str) -> bool:
    """
    Validate that a path does not contain directory traversal.
    
    Args:
        path: The path to validate
        
    Returns:
        True if path is safe, False otherwise
    """
    # Reject paths with directory traversal patterns
    if ".." in path:
        return False
    
    # Reject absolute paths
    if path.startswith("/"):
        return False
    
    # Reject Windows-style absolute paths
    if len(path) >= 2 and path[1] == ":":
        return False
    
    return True
```

### Security Measures

1. **Pattern Detection:** Reject any path containing `..`
2. **Absolute Path Rejection:** Reject paths starting with `/` or drive letters
3. **Path Resolution:** Use `pathlib.Path` for safe path manipulation
4. **Project Root Scoping:** All paths resolved relative to project root
5. **Error Handling:** Return descriptive errors for invalid paths

### Example Valid/Invalid Paths

| Path | Valid? | Reason |
|------|--------|--------|
| `wiki/git-workflow.md` | ✅ | Valid relative path |
| `wiki` | ✅ | Valid directory |
| `../secret.txt` | ❌ | Directory traversal |
| `wiki/../../../etc/passwd` | ❌ | Directory traversal |
| `/etc/passwd` | ❌ | Absolute path |
| `C:\Windows\system32` | ❌ | Windows absolute path |

## System Prompt Design for Documentation Discovery

### Prompt Strategy

The system prompt guides the LLM to:
1. Use available tools to discover documentation
2. Reference specific wiki sections in answers
3. Provide accurate, sourced information

### System Prompt

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

### Output Format

The agent returns JSON with the following structure:

```json
{
  "answer": "To resolve merge conflicts, follow these steps: ...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "File contents..."
    }
  ]
}
```

## Implementation Steps

1. **Define Tool Schemas**
   - Create tool definitions in OpenAI format
   - Implement `read_file` function with path validation
   - Implement `list_files` function with path validation

2. **Implement Agentic Loop**
   - Modify `call_llm` to support tool calls
   - Add tool execution logic
   - Implement message history tracking
   - Add max tool calls limit

3. **Update Output Format**
   - Add `source` field to output JSON
   - Track all tool calls for output
   - Maintain backward compatibility

4. **Write Tests**
   - Test merge conflicts question → expects `read_file`
   - Test "What files in wiki?" → expects `list_files`
   - Use mocking for file system access

5. **Update Documentation**
   - Document tools in AGENT.md
   - Explain agentic loop architecture
   - Provide usage examples

## Testing Strategy

### Regression Tests

1. **Test: Merge Conflicts Question**
   - Input: "How do I resolve merge conflicts?"
   - Expected: `read_file` in tool_calls
   - Expected: `wiki/git-workflow.md` in source

2. **Test: Wiki Files Question**
   - Input: "What files are in the wiki?"
   - Expected: `list_files` in tool_calls

### Mocking Strategy

- Mock `read_file` and `list_files` to avoid actual file access
- Mock LLM API responses with predetermined tool calls
- Verify tool call structure and count

## Git Operations

```bash
# Create and checkout branch
git checkout -b task/2-documentation-agent

# Stage all changes
git add plans/task-2.md agent.py AGENT.md tests/test_agent.py

# Commit
git commit -m "feat: add documentation agent with file tools"

# Push
git push origin task/2-documentation-agent
```
