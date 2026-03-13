# Task 3: System Agent

## Overview

This task extends the Documentation Agent from Task 2 with a `query_api` tool that enables the agent to interact with the deployed backend API. The agent can now query the Learning Management Service (LMS) API to retrieve system data, analytics scores, and other information.

## query_api Tool Schema Implementation

### Tool Definition (OpenAI Function Calling Format)

The `query_api` tool is implemented using the OpenAI-compatible function calling schema:

```python
{
    "type": "function",
    "function": {
        "name": "query_api",
        "description": "Call the deployed backend API to get system data",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP method"
                },
                "path": {
                    "type": "string",
                    "description": "API endpoint path (e.g., '/items/', '/analytics/scores?lab=lab-04')"
                },
                "body": {
                    "type": "string",
                    "description": "Optional JSON request body for POST/PUT requests"
                }
            },
            "required": ["method", "path"]
        }
    }
}
```

### Tool Implementation Details

**Purpose:** Makes HTTP requests to the deployed backend API at `http://localhost:42002` (or configured URL).

**Parameters:**
- `method` (required): HTTP method - GET, POST, PUT, or DELETE
- `path` (required): API endpoint path relative to the base URL
- `body` (optional): JSON string for POST/PUT request bodies

**Return Value:** Structured response containing:
- `success`: Boolean indicating request success
- `status_code`: HTTP status code
- `data`: Response data (parsed JSON or text)
- `error`: Error message if request failed

**Example Usage:**
```python
query_api({
    "method": "GET",
    "path": "/analytics/scores?lab=lab-04"
})
```

## Authentication Strategy

### LMS_API_KEY Authentication

The backend API requires authentication using the `LMS_API_KEY` from `.env.docker.secret`:

```env
LMS_API_KEY=2e5a479aaf7a0502b9a645ae8aba39fd3d2f74dfb5dedf59f9415ccc25f158bc
```

### Authentication Header

All API requests include the API key in the `X-API-Key` header:

```python
headers = {
    "X-API-Key": config['lms_api_key'],
    "Content-Type": "application/json"
}
```

### Key Management

- API key is loaded from `.env.docker.secret` (gitignored)
- Key is passed to the agent via environment variable or config file
- Never hardcode the API key in source code

## Environment Variables Handling

### Configuration File: .env.agent.secret

The agent loads configuration from `.env.agent.secret`:

```env
# LLM Configuration (from Task 1/2)
LLM_API_KEY=sk-or-v1-...
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=alibaba/qwen3-coder-plus

# Backend API Configuration (NEW for Task 3)
AGENT_API_BASE_URL=http://localhost:42002
```

### AGENT_API_BASE_URL

- **Default:** `http://localhost:42002`
- **Purpose:** Base URL for the deployed backend API
- **Override:** Autochecker will override this value during testing
- **Usage:** All API paths are appended to this base URL

### Configuration Loading

```python
def load_config():
    """Load configuration from .env.agent.secret file."""
    load_dotenv('.env.agent.secret')
    return {
        'api_key': os.getenv('LLM_API_KEY'),
        'api_base': os.getenv('LLM_API_BASE'),
        'model': os.getenv('LLM_MODEL'),
        'api_base_url': os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
    }
```

## System Prompt Updates for Tool Selection

### Updated System Prompt

The system prompt is updated to guide the LLM in selecting the appropriate tool for API queries:

```
You are a System Agent that helps users find information from both the project wiki and the deployed backend API.

You have access to three tools:
- read_file: Read the contents of a file from the project repository
- list_files: List files and directories at a given path
- query_api: Call the deployed backend API to get system data

When answering questions:
1. For questions about system data, analytics, scores, or items - use query_api
2. For questions about documentation - use read_file and list_files
3. Always cite your sources:
   - For API responses: mention the API endpoint used
   - For wiki files: use format wiki/<filename>.md#<section>
4. Use GET method for retrieving data, POST for creating, PUT for updating, DELETE for removing
5. Provide clear, accurate answers based on the data you retrieve

Important:
- API base URL is configured in your environment
- Paths should include leading slash (e.g., '/items/', '/analytics/scores')
- For query parameters, include them in the path (e.g., '/analytics/scores?lab=lab-04')
- Request body should be a valid JSON string for POST/PUT requests
```

### Tool Selection Strategy

| Question Type | Tool | Example |
|--------------|------|---------|
| System data, items | `query_api` (GET) | "What items are in the system?" |
| Analytics scores | `query_api` (GET) | "Get scores for lab-04" |
| Create new item | `query_api` (POST) | "Create a new item with name 'Test'" |
| Update item | `query_api` (PUT) | "Update item 1 with new data" |
| Delete item | `query_api` (DELETE) | "Delete item 5" |
| Documentation | `read_file` | "How do I resolve merge conflicts?" |
| Explore wiki | `list_files` | "What files are in the wiki?" |

## Initial Benchmark Score and Iteration Strategy

### Benchmark Questions

Test the agent with the following questions to establish baseline performance:

1. **GET Request:** "What items are available in the system?"
   - Expected: `query_api` with GET method to `/items/`

2. **Analytics Query:** "Show me the analytics scores for lab-04"
   - Expected: `query_api` with GET to `/analytics/scores?lab=lab-04`

3. **POST Request:** "Create a new item with name 'Test Item'"
   - Expected: `query_api` with POST to `/items/` and JSON body

4. **Documentation Query:** "How do I use Docker?"
   - Expected: `read_file` or `list_files` for wiki/docker.md

### Iteration Strategy

1. **Initial Implementation:**
   - Add `query_api` tool schema
   - Implement HTTP request logic with authentication
   - Update system prompt
   - Test with benchmark questions

2. **Error Handling Improvements:**
   - Handle connection errors gracefully
   - Parse API error responses
   - Provide meaningful error messages to LLM

3. **Tool Selection Refinement:**
   - Analyze cases where LLM chooses wrong tool
   - Refine system prompt for better tool selection
   - Add examples to system prompt if needed

4. **Performance Optimization:**
   - Reduce unnecessary API calls
   - Cache frequently accessed data if appropriate
   - Optimize prompt length for faster responses

5. **Testing and Validation:**
   - Run autochecker tests
   - Fix any failing test cases
   - Document edge cases and limitations

## Implementation Steps

1. **Add query_api Tool Schema**
   - Define tool in OpenAI function calling format
   - Add to TOOLS array in agent.py

2. **Implement query_api Function**
   - Use `requests` library for HTTP calls
   - Include authentication header with LMS_API_KEY
   - Handle JSON and text responses
   - Implement error handling

3. **Update Configuration**
   - Add AGENT_API_BASE_URL to .env.agent.example
   - Load API key from .env.docker.secret
   - Update load_config() function

4. **Update System Prompt**
   - Add query_api tool description
   - Provide guidance on tool selection
   - Include API usage examples

5. **Update execute_tool Function**
   - Add case for query_api
   - Pass method, path, body to implementation

6. **Write Tests**
   - Test GET requests to various endpoints
   - Test POST/PUT/DELETE requests
   - Test error handling
   - Test authentication header

7. **Update Documentation**
   - Update AGENT.md with query_api details
   - Document API endpoints
   - Provide usage examples

## Git Operations

```bash
# Create and checkout branch
git checkout -b task/3-system-agent

# Stage all changes
git add plans/task-3.md agent.py .env.agent.example AGENT.md

# Commit
git commit -m "feat: add system agent with query_api tool"

# Push
git push origin task/3-system-agent
```

## API Endpoints Reference

Based on the LMS backend, available endpoints include:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/items/` | List all items |
| GET | `/items/{id}/` | Get specific item |
| POST | `/items/` | Create new item |
| PUT | `/items/{id}/` | Update item |
| DELETE | `/items/{id}/` | Delete item |
| GET | `/analytics/scores` | Get analytics scores |
| GET | `/analytics/scores?lab=lab-04` | Get scores for specific lab |
| GET | `/interactions/` | List interactions |
| GET | `/learners/` | List learners |

## Error Handling Strategy

### HTTP Errors

| Status Code | Handling |
|-------------|----------|
| 200-299 | Success - return parsed data |
| 400 | Bad Request - return error message from API |
| 401 | Unauthorized - check API key configuration |
| 404 | Not Found - endpoint or resource doesn't exist |
| 500 | Server Error - backend issue |
| Connection Error | Backend not running at configured URL |

### Response Format

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
  "error": "Item not found"
}
```
