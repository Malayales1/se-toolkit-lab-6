# CLI Agent for Lab 6 - Task 1

## Overview

This agent provides a simple CLI interface for calling the Qwen Code API to answer questions.

## LLM Provider and Model

- **Provider:** Qwen Code API (Dashscope)
- **Model:** `qwen3-coder-plus`
- **API Base:** `https://dashscope.aliyuncs.com/compatible-mode/v1`

The agent uses the OpenAI-compatible chat completions API for seamless integration.

## How It Works

1. The agent reads configuration from `.env.agent.secret`
2. Accepts a question as a command-line argument
3. Calls the Qwen Code API with the question
4. Outputs a JSON response to stdout

## Setup Instructions

### 1. Create Environment File

Copy the example file and fill in your credentials:

```bash
cp .env.agent.example .env.agent.secret
```

### 2. Configure Credentials

Edit `.env.agent.secret` with your Dashscope API credentials:

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx  # Get from https://dashscope.console.aliyun.com/
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-coder-plus
```

**To get your API key:**
1. Go to [Dashscope Console](https://dashscope.console.aliyun.com/)
2. Sign in with your Alibaba Cloud account
3. Navigate to API Key Management
4. Create or copy your API key (starts with `sk-`)

### 3. Install Dependencies

The project uses `uv` for dependency management. Required packages:

```bash
uv add openai python-dotenv
```

## Usage

Run the agent with a question:

```bash
uv run agent.py "What is REST?"
```

### Output Format

The agent outputs valid JSON to stdout:

```json
{
  "answer": "REST (Representational State Transfer) is an architectural style...",
  "tool_calls": []
}
```

### Error Handling

- All error messages are written to stderr
- Exit code 0 on success
- Exit code 1 on error (missing arguments, configuration errors, API errors)

## Testing

Run tests with pytest:

```bash
uv run pytest tests/test_agent.py -v
```

## File Structure

```
se-toolkit-lab-6/
├── agent.py              # Main agent script
├── AGENT.md              # This documentation
├── .env.agent.example    # Example environment file
├── .env.agent.secret     # Actual credentials (gitignored)
├── plans/
│   └── task-1.md         # Implementation plan
└── tests/
    └── test_agent.py     # Pytest tests
```
