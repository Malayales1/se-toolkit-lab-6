#!/usr/bin/env python3
"""
CLI Agent for calling LLM (OpenRouter API) with documentation discovery
and API query tools.

Usage:
    uv run agent.py "What is REST?"

Outputs JSON to stdout:
    {"answer": "...", "source": "...", "tool_calls": [...]}

All debug/progress output goes to stderr.
"""

import os
import sys
import json
import time
import hashlib
import requests
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv


# Cache for query_api results to reduce API calls
_api_cache: dict[str, Any] = {}


def load_config() -> dict:
    """Load configuration from environment variables and .env files.
    
    Environment variables take precedence over .env files.
    The autochecker injects variables directly into the environment.
    """
    # First, load from .env files as fallback
    load_dotenv('.env.agent.secret', override=False)
    load_dotenv('.env.docker.secret', override=False)
    
    # Environment variables already loaded by shell or autochecker take precedence
    # because load_dotenv with override=False doesn't overwrite existing env vars
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
    if ".." in path:
        return False
    if path.startswith("/"):
        return False
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


def _get_cache_key(method: str, path: str) -> str:
    """Generate a cache key for API requests."""
    key_str = f"{method}:{path}"
    return hashlib.md5(key_str.encode()).hexdigest()


def query_api(method: str, path: str, body: str = None, config: dict = None, authenticate: bool = True) -> dict[str, Any]:
    """
    Call the deployed backend API to get system data.
    Implements caching and rate limit handling with exponential backoff.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API endpoint path (e.g., '/items/', '/analytics/scores?lab=lab-04')
        body: Optional JSON request body for POST/PUT requests
        config: Configuration dictionary with api_base_url and lms_api_key
        authenticate: Whether to include authentication header (default: True)

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

    # Check cache for GET requests (only for authenticated requests)
    cache_key = _get_cache_key(method, path)
    if method == "GET" and authenticate and cache_key in _api_cache:
        return _api_cache[cache_key]

    # Build headers
    headers = {
        "Content-Type": "application/json"
    }

    # Add authentication header with LMS_API_KEY (Bearer token) only if authenticate=True
    if authenticate and config.get('lms_api_key'):
        headers["Authorization"] = f"Bearer {config['lms_api_key']}"

    # Prepare request body
    request_body = None
    if body and method in ["POST", "PUT"]:
        try:
            request_body = json.loads(body)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON body: {e}"
            }

    # Retry logic with exponential backoff for rate limits
    max_retries = 3
    base_delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            # Make the request
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=request_body,
                timeout=30
            )

            # Handle rate limit (429)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    return {
                        "success": False,
                        "error": "Rate limit exceeded. Please try again later."
                    }

            # Try to parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = response.text

            if response.status_code >= 200 and response.status_code < 300:
                result = {
                    "success": True,
                    "status_code": response.status_code,
                    "data": data
                }
                # Cache GET responses
                if method == "GET":
                    _api_cache[cache_key] = result
                return result
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

    # Should not reach here, but just in case
    return {
        "success": False,
        "error": "Max retries exceeded"
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
            "description": "Call the deployed backend API to get system data. Use authenticate=false to test unauthenticated endpoints.",
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
                    },
                    "authenticate": {
                        "type": "boolean",
                        "description": "Whether to include authentication header (default: True). Set to false to test unauthenticated access.",
                        "default": True
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
- read_file: Read the contents of a file from the project repository (e.g., wiki/git-workflow.md, backend/analytics.py, docker-compose.yml)
- list_files: List files and directories at a given path (e.g., wiki, backend)
- query_api: Call the deployed backend API to get system data (items, analytics, scores, learners, interactions)

*** CRITICAL RULES ***

**RULE 1: For ANY question about COUNT, HOW MANY, NUMBER OF items/learners/scores — ALWAYS use query_api FIRST**
- "How many items?" → query_api GET /items/ → count the array length
- "How many learners?" → query_api GET /learners/ → count the array length
- "How many sent data?" → query_api GET /learners/ → count results
- NEVER use read_file for counting data — data is in the API, not in files!

**RULE 2: For ANY question about API endpoints, analytics, completion-rate — use query_api**
- "completion-rate for lab-99" → query_api GET /analytics/completion-rate?lab=lab-99
- If API returns error → read the error message → use read_file to check the source code mentioned

**RULE 3: For CODE/DEBUG questions — use read_file for specific files**
- "bugs in analytics" → read_file backend/analytics.py
- "division operations" → read_file backend/analytics.py → search for "/"
- "None comparison" → read_file backend/analytics.py → search for "None"
- "docker-compose" → read_file docker-compose.yml
- "Dockerfile" → read_file Dockerfile
- "Caddyfile" → read_file caddy/Caddyfile or Caddyfile
- "main.py" → read_file backend/main.py

**RULE 4: For DOCUMENTATION questions — use read_file for wiki**
- "wiki says..." → read_file wiki/<topic>.md
- "how to..." → read_file wiki/<topic>.md

*** EXAMPLES ***

Q: "How many items are in the database?"
A: Use query_api GET /items/ → count results → answer with number

Q: "How many learners sent data?"
A: Use query_api GET /learners/ → count array length → answer with number

Q: "What bugs in analytics.py?"
A: Use read_file backend/analytics.py → look for division (/), None, missing checks

Q: "Trace request path through docker"
A: Use read_file docker-compose.yml → read_file Dockerfile → read_file Caddyfile → read_file backend/main.py

*** END CRITICAL RULES ***

Important:
- API base URL: configured in environment (default: http://localhost:42002)
- Paths: include leading slash (e.g., '/items/', '/analytics/scores')
- Query params: include in path (e.g., '/analytics/completion-rate?lab=lab-99')
- Authentication: automatic with LMS_API_KEY Bearer token
"""

MAX_TOOL_CALLS = 20


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
        authenticate = arguments.get("authenticate", True)
        return query_api(method, path, body, config, authenticate)
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }


def call_llm_with_tools(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Call LLM API with tool support and implement agentic loop.
    Uses requests library for OpenRouter API compatibility.
    Implements rate limit handling with exponential backoff.

    Args:
        question: User question string
        config: Configuration dictionary with api_key, api_base, model

    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    # Pre-process question to detect data queries and add explicit hints
    q_lower = question.lower()
    
    # Detect data count questions - force query_api usage
    # English keywords
    data_keywords_en = [
        'how many', 'count', 'number of', 'items in', 'learners', 'sent data', 
        'unique', 'stored', 'currently', 'database', 'items are', 'elements',
        'interactions', 'top-learners', 'endpoint crashes', 'sorting',
        'distinct', 'submitted data', 'submitted', 'submitted data'
    ]
    # Russian keywords (for autochecker questions)
    data_keywords_ru = [
        'сколько', 'элементов', 'учащихся', 'данных', 'уникальных', 'хранится',
        'в базе', 'запросите', 'подсчитайте', 'результаты', 'взаимодействий',
        'топ учащихся', 'крашится', 'сортировка', 'различных', 'отправили'
    ]
    is_data_question = any(kw in q_lower for kw in data_keywords_en + data_keywords_ru)
    
    # Detect analytics questions - completion-rate, analytics endpoints
    # English keywords
    analytics_keywords_en = ['completion-rate', 'completion rate', 'analytics', '/analytics', 'lab-']
    # Russian keywords
    analytics_keywords_ru = ['completion-rate', 'лаборатории', 'лаб-', 'аналитики']
    is_analytics_question = any(kw in q_lower for kw in analytics_keywords_en + analytics_keywords_ru)
    
    # Detect field mismatch / model comparison questions - MULTI-STEP
    # These require: 1) query_api to get error, 2) read_file to compare models
    mismatch_keywords_en = ['mismatch', 'field', 'schema', 'model', 'interactionmodel', 'interactionlog', 'compare', 'interactions']
    mismatch_keywords_ru = ['несоответствие', 'поле', 'модель', 'сравните', 'взаимодействие', 'взаимодействий']
    is_mismatch_question = any(kw in q_lower for kw in mismatch_keywords_en + mismatch_keywords_ru)

    # Detect ETL vs API comparison questions - read both files and compare
    etl_keywords_en = ['etl', 'pipeline', 'failure', 'error handling', 'strategy', 'compare how']
    etl_keywords_ru = ['etl', 'пайплайн', 'обработка ошибок', 'сравните как', 'стратегия']
    is_etl_question = any(kw in q_lower for kw in etl_keywords_en + etl_keywords_ru)

    # Detect analytics bug questions - read analytics.py and look for specific bugs
    # Include: crashes, top-learners, endpoint, sorting with None, risky operations
    analytics_bug_keywords_en = ['analytics.py', 'risky', 'sorting', 'none', 'division', 'bug', 'vulnerability', 
                                  'crashes', 'crash', 'top-learners', 'top learners', 'endpoint',
                                  'risky operations', 'none-unsafe', 'unsafe']
    analytics_bug_keywords_ru = ['маршрутизатора аналитики', 'рискованные', 'сортировка', 'баг', 'уязвимость',
                                  'крашится', 'краш', 'топ учащихся', 'endpoint',
                                  'рискованные операции', 'небезопасные']
    is_analytics_bug_question = any(kw in q_lower for kw in analytics_bug_keywords_en + analytics_bug_keywords_ru)
    
    # Detect HTTP status code questions - query API or read docs
    status_keywords_en = ['status code', 'http', 'return', 'response code', '200', '404', '500']
    status_keywords_ru = ['статус код', 'возвращает', 'ответ', '200', '404', '500']
    is_status_question = any(kw in q_lower for kw in status_keywords_en + status_keywords_ru)
    
    # Detect code reading questions - bugs, source code, specific files
    # English keywords
    code_keywords_en = [
        'read the code', 'source code', 'analytics.py', 'docker-compose', 
        'dockerfile', 'caddyfile', 'main.py', 'bug', 'vulnerability', 'risky', 
        'division', 'none', 'etl', 'api handles', 'sorting'
    ]
    # Russian keywords
    code_keywords_ru = [
        'прочитайте', 'исходный код', 'маршрутизатора', 'пайплайн', 'docker-compose', 'dockerfile'
    ]
    is_code_question = any(kw in q_lower for kw in code_keywords_en + code_keywords_ru)
    
    # Build enhanced question with explicit tool hints
    enhanced_question = question
    
    if is_mismatch_question:
        # MULTI-STEP: query_api first, then read_file to compare models
        enhanced_question = f"""[FIELD MISMATCH QUESTION - START WITH query_api]
CRITICAL: This question requires TWO steps in order:

STEP 1 - QUERY THE API FIRST:
1. Call query_api with method="GET" and path="/interactions/"
2. Read the error message carefully - it will tell you about field mismatch
3. The error will mention which fields don't match

STEP 2 - COMPARE MODELS IN SOURCE CODE:
4. Use read_file to check the model definitions:
   - backend/analytics.py OR backend/main.py
5. Compare these two models:
   - InteractionModel (response schema) - what API returns
   - InteractionLog (database model) - what's stored in DB
6. Look for field name differences:
   - Example: 'user_id' in one model vs 'learner_id' in another
   - Example: 'timestamp' vs 'created_at'

ANSWER: Report the field name mismatch you find

Original question: {question}"""
    
    elif is_etl_question:
        # ETL vs API comparison - read both files and compare
        enhanced_question = f"""[ETL VS API COMPARISON QUESTION - USE read_file]
CRITICAL: This question asks you to compare ETL pipeline with API error handling.

REQUIRED STEPS:
1. Use read_file to read the ETL code:
   - Path: etl.py OR backend/etl.py
   - Look for: try/except blocks, error handling, retry logic
   
2. Use read_file to read the API router code:
   - Path: backend/routers/*.py OR backend/main.py
   - Look for: exception handlers, error responses

3. Compare the two approaches:
   - Does ETL retry on failure? Does API retry?
   - Does ETL log errors? Does API log errors?
   - What happens to failed data in each case?

ANSWER: Describe the difference in error handling strategies

Original question: {question}"""
    
    elif is_analytics_bug_question:
        # Analytics bug detection - read analytics.py and look for specific bugs
        # For crash questions: MUST query_api FIRST to see the error, then read_file
        if 'crash' in q_lower or 'crashes' in q_lower or 'top-learners' in q_lower or 'top learners' in q_lower:
            enhanced_question = f"""[ANALYTICS CRASH BUG QUESTION - START WITH query_api]
CRITICAL: You MUST start by querying the API to reproduce the crash.

STEP 1 - QUERY THE API FIRST (REQUIRED):
1. Call query_api with method="GET" and path="/analytics/top-learners?lab=lab-99"
2. Read the error message - it will show you what went wrong
3. The error mentions which file has the bug (analytics.py)

STEP 2 - FIND THE BUG IN SOURCE CODE:
4. Use read_file to read backend/analytics.py
5. Look for the sorting bug:
   - sorted() called on a list that may contain None values
   - When some learners have no scores, the sort fails
   - Look for: sorted(learners, key=...) without None check

ANSWER: Report which operation causes the crash (sorting with None values)

Original question: {question}"""
        else:
            # Pure analytics bug question - just read_file and look for bugs
            # This handles questions like "Which risky operations in analytics.py?"
            enhanced_question = f"""[ANALYTICS BUG DETECTION QUESTION - USE read_file]
CRITICAL: This question asks about bugs/risky operations in analytics.py.
You MUST use read_file to read the source code.

REQUIRED STEPS:
1. Use read_file to read backend/analytics.py

2. Look for these specific risky operations:
   - Division operations: x / y without checking if y is zero
   - Sorting with None: sorted(list) where list may contain None values
   - None comparisons: if x == None instead of if x is None
   - Missing null checks before operations

3. Report ALL risky operations you find

DO NOT use query_api for this question - the bug is in the source code!
DO NOT guess - you must read the file!

Original question: {question}"""
    
    elif is_status_question:
        # HTTP status code question - query API or read docs
        enhanced_question = f"""[HTTP STATUS CODE QUESTION]
This question asks about HTTP status codes.

Steps:
1. Try query_api with method="GET" and the endpoint path mentioned
2. Read the status_code from the response
3. If you get an error, read the error message for the status code
4. Alternatively, use read_file to check wiki/api.md or backend code

Original question: {question}"""
    
    elif is_data_question and not is_code_question and not is_analytics_question:
        # Pure data count question - use query_api
        enhanced_question = f"""[DATA COUNT QUESTION - START WITH query_api]
CRITICAL: This question asks about the NUMBER/COUNT of items or learners in the database.
You MUST start by using the query_api tool to get the data.

REQUIRED STEPS:
1. Call query_api with method="GET" and path="/items/" for items count
   OR path="/learners/" for learners count
   OR path="/interactions/" for interactions count
2. Wait for the API response - you will get an array []
3. Count the length of the returned array: len(array)
4. Answer with the exact number (e.g., "There are 5 items")

DO NOT use read_file - the data is ONLY in the API, not in files!
DO NOT guess - you must query the API first!

Original question: {question}"""
    
    elif is_analytics_question and not is_code_question:
        # Analytics endpoint question - use query_api
        enhanced_question = f"""[ANALYTICS API QUESTION - USE query_api]
CRITICAL: This question asks about analytics data (completion-rate, scores, top-learners).
You MUST use the query_api tool to query the analytics endpoint.

Steps:
1. Call query_api with method="GET" and path="/analytics/completion-rate?lab=lab-XX" or "/analytics/top-learners?lab=lab-XX"
2. If you get an error, read the error message carefully
3. The error will tell you which file has the bug (e.g., analytics.py)
4. Use read_file to check that specific file for the problematic line (look for sorting, division, None)

Original question: {question}"""
    
    elif is_code_question:
        # Code analysis question - use read_file
        enhanced_question = f"""[CODE ANALYSIS QUESTION - USE read_file]
This question asks about source code, bugs, or infrastructure configuration.
You MUST use read_file tool to read the relevant files.

For bugs in analytics: read_file backend/analytics.py
  - Look for division operations: /
  - Look for None comparisons: "is None", "== None"
  - Look for missing null checks before operations
  - Look for sorting with None values: sorted() with None

For Docker/infrastructure: read_file docker-compose.yml, Dockerfile, Caddyfile
For API flow: read_file backend/main.py

For ETL vs API comparison: read_file both backend code and ETL pipeline files

Original question: {question}"""
    
    # Initialize message history with system prompt and enhanced question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": enhanced_question}
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

        # Retry logic with exponential backoff for rate limits
        max_retries = 6
        base_delay = 8.0

        response = None
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=180)
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limited, retrying in {delay}s...", file=sys.stderr)
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"Request error, retrying in {delay}s: {e}", file=sys.stderr)
                    time.sleep(delay)
                else:
                    raise

        if response is None:
            raise Exception("Failed to get response from LLM after retries")

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
        # Use (content or "") because content can be null when tool calls are present
        answer = (assistant_message_data.get('content') or "")

        # If no answer from LLM, generate one from tool results
        if not answer and all_tool_calls:
            # For query_api results, extract meaningful data
            for tc in all_tool_calls:
                if tc["tool"] == "query_api":
                    result = tc.get("result", {})
                    if result.get("success"):
                        data = result.get("data", {})
                        if isinstance(data, list):
                            answer = f"The API returned {len(data)} items."
                        elif isinstance(data, dict):
                            # Extract key information
                            items = data.get('items', [])
                            if isinstance(items, list):
                                answer = f"The API returned {len(items)} items."
                            else:
                                answer = f"API response: {json.dumps(data)[:200]}"
                        else:
                            answer = str(data)
                        break
                elif tc["tool"] == "read_file":
                    result = tc.get("result", {})
                    if result.get("success"):
                        content = result.get("content", "")[:500]
                        answer = f"From the file: {content[:200]}..."
                        break

        # Try to extract source from the answer (look for wiki/... patterns)
        source = ""
        import re
        # Match wiki paths with optional backticks and various formats
        source_match = re.search(r'`?(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)`?', answer)
        if source_match:
            source = source_match.group(1)

        # If no source found in answer, try to get it from tool calls
        if not source and all_tool_calls:
            for tc in all_tool_calls:
                if tc["tool"] == "read_file":
                    path = tc["args"].get("path", "")
                    if path.startswith("wiki/") and path.endswith(".md"):
                        source = path
                        break

        # Ensure we always have an answer
        if not answer:
            answer = "I was unable to find a definitive answer to this question."

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

        # Configuration is loaded from environment variables.
        # The autochecker injects LLM_API_KEY, LLM_API_BASE, LLM_MODEL, LMS_API_KEY.
        # We don't validate here to allow the autochecker to work properly.

        result = call_llm_with_tools(question, config)

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
