# Task 1: Call an LLM from Code

## LLM Provider Choice

**Selected Provider:** Qwen Code API

**Rationale:**
- OpenAI-compatible API interface (easy integration with existing libraries)
- Recommended for the lab tasks
- Reliable performance and good documentation
- Supports chat completions endpoint

## Model Selection

**Selected Model:** `qwen3-coder-plus`

**Reasons:**
- Optimized for code-related tasks and technical questions
- Good balance between performance and speed
- Supports context windows suitable for typical CLI interactions
- Compatible with OpenAI API format

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CLI Input     │────▶│   agent.py       │────▶│  Qwen Code API  │
│   (question)    │     │                  │     │                 │
└─────────────────┘     │  1. Load config  │     └─────────────────┘
                        │  2. Call LLM     │              │
                        │  3. Parse result │              │
                        │  4. Output JSON  │◀─────────────┘
                        └──────────────────┘
```

### Components:

1. **Configuration Loader** (`load_config`)
   - Reads environment variables from `.env.agent.secret`
   - Provides API key, base URL, and model name

2. **LLM Client** (`call_llm`)
   - Uses OpenAI Python library for API calls
   - Sends chat completion requests
   - Handles response parsing

3. **CLI Interface** (`main`)
   - Accepts question as command-line argument
   - Outputs JSON to stdout
   - Sends debug info to stderr
   - Handles errors gracefully

## Implementation Steps

1. **Setup Environment**
   - Create `.env.agent.example` with template variables
   - Create `.env.agent.secret` with actual credentials
   - Add `.env.agent.secret` to `.gitignore`

2. **Install Dependencies**
   - `openai` - OpenAI-compatible API client
   - `python-dotenv` - Environment variable management

3. **Implement agent.py**
   - Configuration loading function
   - LLM calling function with timeout handling
   - CLI entry point with argument parsing
   - JSON output formatting

4. **Create Documentation**
   - Write `AGENT.md` with usage instructions
   - Document setup process

5. **Write Tests**
   - Create `tests/test_agent.py`
   - Test JSON output structure
   - Verify required fields exist

6. **Git Operations**
   - Create branch `task/1-call-llm`
   - Stage and commit changes
   - Push to remote

## API Configuration

```
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-coder-plus
LLM_API_KEY=<obtained from Qwen Code setup / Dashscope>
```

## Expected Output Format

```json
{
  "answer": "REST is an architectural style...",
  "tool_calls": []
}
```

## Error Handling

- Missing arguments → stderr message, exit code 1
- Configuration errors → stderr message, exit code 1
- API errors → stderr message, exit code 1
- Timeout (>60s) → stderr message, exit code 1
