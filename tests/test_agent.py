"""
Tests for the CLI agent.

Run with: uv run pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path


def get_agent_path():
    """Get the absolute path to agent.py."""
    return Path(__file__).parent.parent / "agent.py"


def test_agent_runs_successfully():
    """Test that the agent runs without errors."""
    agent_path = get_agent_path()
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    # Should exit with code 0
    assert result.returncode == 0, f"Agent failed with stderr: {result.stderr}"


def test_agent_outputs_valid_json():
    """Test that the agent outputs valid JSON."""
    agent_path = get_agent_path()
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is REST?"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    # Should be able to parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}")


def test_agent_output_has_answer_field():
    """Test that the agent output contains 'answer' field."""
    agent_path = get_agent_path()
    result = subprocess.run(
        ["uv", "run", str(agent_path), "Explain API"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    output = json.loads(result.stdout)
    assert "answer" in output, "Output missing 'answer' field"
    assert isinstance(output["answer"], str), "'answer' should be a string"
    assert len(output["answer"]) > 0, "'answer' should not be empty"


def test_agent_output_has_tool_calls_field():
    """Test that the agent output contains 'tool_calls' field."""
    agent_path = get_agent_path()
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is Python?"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    output = json.loads(result.stdout)
    assert "tool_calls" in output, "Output missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"


def test_agent_missing_argument():
    """Test that agent handles missing arguments correctly."""
    agent_path = get_agent_path()
    result = subprocess.run(
        ["uv", "run", str(agent_path)],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    # Should exit with non-zero code
    assert result.returncode != 0
    # Should have error message in stderr
    assert "Usage" in result.stderr or "Error" in result.stderr
