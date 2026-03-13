#!/usr/bin/env python3
"""
CLI Agent for calling LLM (Qwen Code API).

Usage:
    uv run agent.py "What is REST?"

Outputs JSON to stdout:
    {"answer": "...", "tool_calls": []}

All debug/progress output goes to stderr.
"""

import os
import sys
import json
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


def call_llm(question, config):
    """
    Call LLM API with the given question.
    
    Args:
        question: User question string
        config: Configuration dictionary with api_key, api_base, model
        
    Returns:
        str: LLM response content
    """
    client = OpenAI(
        api_key=config['api_key'],
        base_url=config['api_base']
    )
    
    response = client.chat.completions.create(
        model=config['model'],
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Answer questions concisely."},
            {"role": "user", "content": question}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    return response.choices[0].message.content


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
        
        answer = call_llm(question, config)
        
        output = {
            "answer": answer,
            "tool_calls": []
        }
        print(json.dumps(output))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
