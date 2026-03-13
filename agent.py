#!/usr/bin/env python3
"""
CLI Agent for calling LLM (Qwen Code API) with documentation discovery and API query tools.

Usage:
    uv run agent.py "What is REST?"

Outputs JSON to stdout:
    {"answer": "...", "source": "...", "tool_calls": [...]}

All debug/progress output goes to stderr.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI


def load_config():
    """Load configuration from .env.agent.secret and .env.docker.secret files."""
    load_dotenv('.env.agent.secret')
    load_dotenv('.env.docker.secret')
    return {
        'api_key': os.getenv('LLM_API_KEY'),
        'api_base': os.getenv('LLM_API_BASE'),
        'model': os.getenv('LLM_MODEL'),
        'api_base_url': os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002'),
        'lms_api_key': os.getenv('LMS_API_KEY')
    }


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


def get_project_root() -> Path:
    """Get the project root directory (where agent.py is located)."""
    return Path(__file__).parent


def read_file(path: str) -> dict[str, Any]:
    """
    Read a file from the project repository.
    
    Args:
        path: Relative path from project root (e.g., 'wiki/git-workflow.md')
        
    Returns:
        dict with 'success' boolean and either 'content' or 'error' message
    """
    if not is_safe_path(path):
        return {
            "success": False,
            "error": f"Invalid path: directory traversal not allowed. Path: {path}"
        }
    
    project_root = get_project_root()
    full_path = project_root / path
    
    # Ensure the resolved path is still within project root
    try:
        resolved_path = full_path.resolve()
        resolved_root = project_root.resolve()
        if not str(resolved_path).startswith(str(resolved_root)):
            return {
                "success": False,
                "error": f"Invalid path: must be within project root. Path: {path}"
            }
    except (OSError, ValueError) as e:
        return {
            "success": False,
            "error": f"Path resolution error: {e}"
        }
    
    if not full_path.exists():
        return {
            "success": False,
            "error": f"File not found: {path}"
        }
    
    if not full_path.is_file():
        return {
            "success": False,
            "error": f"Not a file: {path}"
        }
    
    try:
        content = full_path.read_text(encoding='utf-8')
        return {
            "success": True,
            "content": content
        }
    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied: {path}"
        }
    except UnicodeDecodeError:
        return {
            "success": False,
            "error": f"Cannot read file (not UTF-8 encoded): {path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error reading file: {e}"
        }


def list_files(path: str) -> dict[str, Any]:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root (e.g., 'wiki')
        
    Returns:
        dict with 'success' boolean and either 'files' list or 'error' message
    """
    if not is_safe_path(path):
        return {
            "success": False,
            "error": f"Invalid path: directory traversal not allowed. Path: {path}"
        }
    
    project_root = get_project_root()
    full_path = project_root / path
    
    # Ensure the resolved path is still within project root
    try:
        resolved_path = full_path.resolve()
        resolved_root = project_root.resolve()
        if not str(resolved_path).startswith(str(resolved_root)):
            return {
                "success": False,
                "error": f"Invalid path: must be within project root. Path: {path}"
            }
    except (OSError, ValueError) as e:
        return {
            "success": False,
            "error": f"Path resolution error: {e}"
        }
    
    if not full_path.exists():
        return {
            "success": False,
            "error": f"Path not found: {path}"
        }
    
    if not full_path.is_dir():
        return {
            "success": False,
            "error": f"Not a directory: {path}"
        }
    
    try:
        items = []
        for item in sorted(full_path.iterdir()):
            item_type = "dir" if item.is_dir() else "file"
            items.append({
                "name": item.name,
                "type": item_type
            })
        return {
            "success": True,
            "files": items
        }
    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied: {path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error listing files: {e}"
        }


def query_api(method: str, path: str, body: str = None, config: dict = None) -> dict[str, Any]:
    """
    Call the deployed backend API to get system data.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API endpoint path (e.g., '/items/', '/analytics/scores?lab=lab-04')
        body: Optional JSON request body for POST/PUT requests
        config: Configuration dictionary with api_base_url and lms_api_key

    Returns:
        dict with 'success' boolean and either 'data' or 'error' message
    """
    if config is None:
        config = load_config()

    # Validate method
    valid_methods = ["GET", "POST", "PUT", "DELETE"]
    if method not in valid_methods:
        return {
            "success": False,
            "error": f"Invalid method: {method}. Must be one of: {', '.join(valid_methods)}"
        }

    # Ensure path starts with /
    if not path.startswith("/"):
        path = "/" + path

    # Build full URL
    base_url = config['api_base_url'].rstrip('/')
    url = f"{base_url}{path}"

    # Build headers
    headers = {
        "Content-Type": "application/json"
    }

    # Add authentication header if API key is available
    if config.get('lms_api_key'):
        headers["Authorization"] = f"Bearer {config['lms_api_key']}"

    # Prepare request body
    request_body = None
    if body and method in ["POST", "PUT"]:
        try:
            # Validate JSON body
            request_body = json.loads(body)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON body: {e}"
            }

    try:
        # Make the request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=request_body,
            timeout=30
        )

        # Try to parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError:
            data = response.text

        if response.status_code >= 200 and response.status_code < 300:
            return {
                "success": True,
                "status_code": response.status_code,
                "data": data
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": data if isinstance(data, str) else json.dumps(data)
            }

    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "error": f"Connection error: Could not connect to {url}. Ensure the backend is running."
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"Timeout: Request to {url} timed out after 30 seconds"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request error: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {e}"
        }


# Tool definitions in OpenAI function calling format
TOOLS = [
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
    },
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
    },
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
]

# System prompt for documentation discovery and API queries
SYSTEM_PROMPT = """You are a System Agent that helps users find information from both the project wiki and the deployed backend API.

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
"""

MAX_TOOL_CALLS = 10


def execute_tool(tool_name: str, arguments: dict[str, Any], config: dict = None) -> dict[str, Any]:
    """
    Execute a tool by name with the given arguments.

    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool
        config: Configuration dictionary (required for query_api)

    Returns:
        Result from the tool execution
    """
    if tool_name == "read_file":
        path = arguments.get("path", "")
        return read_file(path)
    elif tool_name == "list_files":
        path = arguments.get("path", "")
        return list_files(path)
    elif tool_name == "query_api":
        method = arguments.get("method", "GET")
        path = arguments.get("path", "")
        body = arguments.get("body")
        return query_api(method, path, body, config)
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }


def call_llm_with_tools(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Call LLM API with tool support and implement agentic loop.
    Uses requests library for Groq API compatibility.

    Args:
        question: User question string
        config: Configuration dictionary with api_key, api_base, model

    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    # Initialize message history with system prompt and user question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    # Track all tool calls for output
    all_tool_calls = []
    tool_call_count = 0

    # Agentic loop
    while tool_call_count < MAX_TOOL_CALLS:
        # Step 1: Send question + tool definitions to LLM using requests
        url = f"{config['api_base']}/chat/completions"
        headers = {
            'Authorization': f"Bearer {config['api_key']}",
            'Content-Type': 'application/json'
        }
        data = {
            'model': config['model'],
            'messages': messages,
            'temperature': 0.7,
            'max_tokens': 1000
        }
        if TOOLS:
            data['tools'] = TOOLS
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        
        assistant_message_data = response_data['choices'][0]['message']
        
        # Parse tool calls if present
        tool_calls = []
        if 'tool_calls' in assistant_message_data and assistant_message_data['tool_calls']:
            for tc in assistant_message_data['tool_calls']:
                tool_calls.append(type('ToolCall', (), {
                    'id': tc['id'],
                    'function': type('Function', (), {
                        'name': tc['function']['name'],
                        'arguments': tc['function']['arguments']
                    })()
                })())
        
        # Step 2: Check if LLM responded with tool_calls
        if tool_calls:
            # Add assistant message to history
            messages.append({
                "role": "assistant",
                "content": assistant_message_data.get('content'),
                "tool_calls": assistant_message_data['tool_calls']
            })

            # Step 3: Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Execute the tool (pass config for query_api)
                result = execute_tool(tool_name, tool_args, config)

                # Record the tool call
                tool_call_record = {
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                }
                all_tool_calls.append(tool_call_record)

                # Add tool result to message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

                tool_call_count += 1

            # Continue loop - go back to step 1
            continue
        
        # Step 4: LLM responded with text message - final answer
        answer = assistant_message.content or ""
        
        # Try to extract source from the answer (look for wiki/... patterns)
        source = ""
        import re
        source_match = re.search(r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)', answer)
        if source_match:
            source = source_match.group(1)
        
        return {
            "answer": answer,
            "source": source,
            "tool_calls": all_tool_calls
        }
    
    # Max tool calls reached - return partial results
    return {
        "answer": "I reached the maximum number of tool calls. Here's what I found so far...",
        "source": "",
        "tool_calls": all_tool_calls
    }


def main():
    """Main entry point for the CLI agent."""
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    try:
        config = load_config()
        
        # Validate configuration
        if not config['api_key']:
            print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)
        if not config['api_base']:
            print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)
        if not config['model']:
            print("Error: LLM_MODEL not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)
        
        result = call_llm_with_tools(question, config)
        
        print(json.dumps(result, ensure_ascii=False))
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
