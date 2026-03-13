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


class TestDocumentationAgent:
    """Regression tests for Documentation Agent with file tools."""

    def test_merge_conflicts_question_uses_read_file(self):
        """Test that a question about merge conflicts triggers read_file tool."""
        from agent import call_llm_with_tools
        from unittest.mock import MagicMock, patch

        # Mock LLM response that calls read_file tool
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = '{"path": "wiki/git-workflow.md"}'
        mock_tool_call.id = "call_1"

        # First response: tool call
        mock_response_with_tool = MagicMock()
        mock_response_with_tool.choices = [MagicMock()]
        mock_response_with_tool.choices[0].message.tool_calls = [mock_tool_call]
        mock_response_with_tool.choices[0].message.content = None

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.choices = [MagicMock()]
        mock_response_final.choices[0].message.tool_calls = []
        mock_response_final.choices[0].message.content = (
            "To resolve merge conflicts, see wiki/git-workflow.md#resolving-merge-conflicts"
        )

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model'
        }

        with patch('agent.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            # First call returns tool call, second returns final answer
            mock_client.chat.completions.create.side_effect = [
                mock_response_with_tool,
                mock_response_final
            ]

            result = call_llm_with_tools("How do I resolve merge conflicts?", config)

            # Verify read_file was called
            assert len(result["tool_calls"]) >= 1
            assert any(tc["tool"] == "read_file" for tc in result["tool_calls"])
            # Verify source contains expected wiki file
            assert "wiki/git-workflow.md" in result["source"]

    def test_wiki_files_question_uses_list_files(self):
        """Test that a question about wiki files triggers list_files tool."""
        from agent import call_llm_with_tools
        from unittest.mock import MagicMock, patch

        # Mock LLM response that calls list_files tool
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "list_files"
        mock_tool_call.function.arguments = '{"path": "wiki"}'
        mock_tool_call.id = "call_1"

        # First response: tool call
        mock_response_with_tool = MagicMock()
        mock_response_with_tool.choices = [MagicMock()]
        mock_response_with_tool.choices[0].message.tool_calls = [mock_tool_call]
        mock_response_with_tool.choices[0].message.content = None

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.choices = [MagicMock()]
        mock_response_final.choices[0].message.tool_calls = []
        mock_response_final.choices[0].message.content = (
            "The wiki directory contains documentation files about Git, Docker, API, and more."
        )

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model'
        }

        with patch('agent.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            # First call returns tool call, second returns final answer
            mock_client.chat.completions.create.side_effect = [
                mock_response_with_tool,
                mock_response_final
            ]

            result = call_llm_with_tools("What files are in the wiki?", config)

            # Verify list_files was called
            assert len(result["tool_calls"]) >= 1
            assert any(tc["tool"] == "list_files" for tc in result["tool_calls"])

    def test_read_file_security_path_traversal(self):
        """Test that read_file rejects directory traversal attempts."""
        from agent import read_file

        # Test various traversal patterns
        malicious_paths = [
            "../secret.txt",
            "wiki/../../../etc/passwd",
            "wiki/../../.env",
            "..\\secret.txt",
        ]

        for path in malicious_paths:
            result = read_file(path)
            assert result["success"] is False
            assert "directory traversal not allowed" in result["error"]

    def test_list_files_security_path_traversal(self):
        """Test that list_files rejects directory traversal attempts."""
        from agent import list_files

        # Test various traversal patterns
        malicious_paths = [
            "../",
            "wiki/../../",
            "..",
        ]

        for path in malicious_paths:
            result = list_files(path)
            assert result["success"] is False
            assert "directory traversal not allowed" in result["error"]

    def test_read_file_valid_path(self):
        """Test that read_file works with valid paths."""
        from agent import read_file
        from unittest.mock import patch
        from pathlib import Path

        # Mock file existence and content
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=True):
                with patch('pathlib.Path.read_text', return_value="Test content"):
                    result = read_file("wiki/test.md")
                    assert result["success"] is True
                    assert result["content"] == "Test content"

    def test_list_files_valid_path(self):
        """Test that list_files works with valid paths using real wiki directory."""
        from agent import list_files

        # Use the actual wiki directory in the project
        result = list_files("wiki")
        
        assert result["success"] is True
        assert "files" in result
        assert len(result["files"]) > 0
        
        # Verify structure of returned files
        for file_info in result["files"]:
            assert "name" in file_info
            assert "type" in file_info
            assert file_info["type"] in ["file", "dir"]
        
        # Check that expected files exist
        file_names = [f["name"] for f in result["files"]]
        assert "git.md" in file_names or "git-workflow.md" in file_names
