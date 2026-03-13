#!/usr/bin/env python3
"""
CLI Agent for calling LLM (Qwen Code API) with documentation discovery tools.

Usage:
    uv run agent.py "What is REST?"

Outputs JSON to stdout:
    {"answer": "...", "source": "...", "tool_calls": [...]}

All debug/progress output goes to stderr.
"""

import os
import sys
import json
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI


def load_config():
    """Load configuration from .env.agent.secret file."""
    load_dotenv('.env.agent.secret')
    return {
        'api_key': os.getenv('LLM_API_KEY'),
        'api_base': os.getenv('LLM_API_BASE'),
        'model': os.getenv('LLM_MODEL')
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
    }
]

# System prompt for documentation discovery
SYSTEM_PROMPT = """You are a Documentation Agent that helps users find information in the project wiki.

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
"""

MAX_TOOL_CALLS = 10


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a tool by name with the given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool
        
    Returns:
        Result from the tool execution
    """
    if tool_name == "read_file":
        path = arguments.get("path", "")
        return read_file(path)
    elif tool_name == "list_files":
        path = arguments.get("path", "")
        return list_files(path)
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }


def call_llm_with_tools(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Call LLM API with tool support and implement agentic loop.
    
    Args:
        question: User question string
        config: Configuration dictionary with api_key, api_base, model
        
    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    client = OpenAI(
        api_key=config['api_key'],
        base_url=config['api_base']
    )
    
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
        # Step 1: Send question + tool definitions to LLM
        response = client.chat.completions.create(
            model=config['model'],
            messages=messages,
            tools=TOOLS,
            temperature=0.7,
            max_tokens=1000
        )
        
        assistant_message = response.choices[0].message
        
        # Step 2: Check if LLM responded with tool_calls
        if assistant_message.tool_calls:
            # Add assistant message to history
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": assistant_message.tool_calls
            })
            
            # Step 3: Execute each tool call
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Execute the tool
                result = execute_tool(tool_name, tool_args)
                
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
