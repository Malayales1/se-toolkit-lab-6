"""
Tests for the CLI agent.

Run with: uv run pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


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


class TestAgentUnit:
    """Unit tests with mocked LLM API."""
    
    def test_load_config(self):
        """Test configuration loading."""
        from agent import load_config
        from unittest.mock import patch
        
        with patch('agent.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda x: {
                'LLM_API_KEY': 'test-key',
                'LLM_API_BASE': 'https://test.api/v1',
                'LLM_MODEL': 'test-model'
            }.get(x)
            
            config = load_config()
            assert config['api_key'] == 'test-key'
            assert config['api_base'] == 'https://test.api/v1'
            assert config['model'] == 'test-model'
    
    def test_call_llm_structure(self):
        """Test LLM call returns proper structure."""
        from agent import call_llm
        from unittest.mock import MagicMock, patch
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test answer"
        
        with patch('agent.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response
            
            config = {
                'api_key': 'test-key',
                'api_base': 'https://test.api/v1',
                'model': 'test-model'
            }
            
            result = call_llm("Test question?", config)
            assert result == "Test answer"
            mock_client.chat.completions.create.assert_called_once()
    
    def test_main_success(self):
        """Test main function with successful execution."""
        from agent import main
        from unittest.mock import patch, MagicMock
        import io
        import sys
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test answer"
        
        with patch('sys.argv', ['agent.py', 'Test question?']):
            with patch('agent.load_config') as mock_load:
                mock_load.return_value = {
                    'api_key': 'test-key',
                    'api_base': 'https://test.api/v1',
                    'model': 'test-model'
                }
                with patch('agent.OpenAI') as mock_openai:
                    mock_client = MagicMock()
                    mock_openai.return_value = mock_client
                    mock_client.chat.completions.create.return_value = mock_response
                    
                    captured = io.StringIO()
                    with patch('sys.stdout', captured):
                        main()
                    
                    output = json.loads(captured.getvalue())
                    assert "answer" in output
                    assert "tool_calls" in output
                    assert output["answer"] == "Test answer"
    
    def test_main_missing_config(self):
        """Test main function with missing config."""
        from agent import main
        from unittest.mock import patch
        import io
        import sys
        
        with patch('sys.argv', ['agent.py', 'Test question?']):
            with patch('agent.load_config') as mock_load:
                mock_load.return_value = {'api_key': None, 'api_base': None, 'model': None}
                
                with patch('sys.stderr', io.StringIO()) as mock_stderr:
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 1
