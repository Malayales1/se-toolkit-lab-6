"""
Tests for the CLI agent.

Run with: pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


def get_agent_path():
    """Get the absolute path to agent.py."""
    return Path(__file__).parent.parent / "agent.py"


def get_python_executable():
    """Get the Python executable path."""
    return sys.executable


def _create_mock_response(content="Test answer", tool_calls=None):
    """Helper to create mock LLM response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'choices': [{
            'message': {
                'content': content,
                'tool_calls': tool_calls or []
            }
        }]
    }
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 200
    return mock_response


def _run_agent_with_mock(question: str):
    """Run agent with mocked LLM API using conftest-style approach."""
    # Create a wrapper script that mocks the API
    wrapper_code = '''
import sys
from unittest.mock import MagicMock, patch

# Create mock response
mock_response = MagicMock()
mock_response.json.return_value = {
    'choices': [{
        'message': {
            'content': ''' + json.dumps(_create_mock_response(question).json.return_value['choices'][0]['message']['content']) + ''',
            'tool_calls': []
        }
    }]
}
mock_response.raise_for_status = MagicMock()
mock_response.status_code = 200

with patch('agent.requests.post') as mock_post:
    mock_post.return_value = mock_response
    from agent import main
    sys.argv = ['agent.py', ''' + json.dumps(question) + ''']
    main()
'''
    python_exe = get_python_executable()
    result = subprocess.run(
        [python_exe, '-c', wrapper_code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=get_agent_path().parent
    )
    return result


def test_agent_runs_successfully():
    """Test that the agent runs without errors."""
    result = _run_agent_with_mock("What is 2+2?")
    assert result.returncode == 0, f"Agent failed with stderr: {result.stderr}"


def test_agent_outputs_valid_json():
    """Test that the agent outputs valid JSON."""
    result = _run_agent_with_mock("What is REST?")
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}")


def test_agent_output_has_answer_field():
    """Test that the agent output contains 'answer' field."""
    result = _run_agent_with_mock("Explain API")
    
    output = json.loads(result.stdout)
    assert "answer" in output, "Output missing 'answer' field"
    assert isinstance(output["answer"], str), "'answer' should be a string"
    assert len(output["answer"]) > 0, "'answer' should not be empty"


def test_agent_output_has_tool_calls_field():
    """Test that the agent output contains 'tool_calls' field."""
    result = _run_agent_with_mock("What is Python?")
    
    output = json.loads(result.stdout)
    assert "tool_calls" in output, "Output missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"


def test_agent_missing_argument():
    """Test that agent handles missing arguments correctly."""
    agent_path = get_agent_path()
    python_exe = get_python_executable()
    result = subprocess.run(
        [python_exe, str(agent_path)],
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

        # Don't mock - let it load from actual env files
        config = load_config()
        assert 'api_key' in config
        assert 'api_base' in config
        assert 'model' in config
        assert 'api_base_url' in config
        assert 'lms_api_key' in config

    def test_main_success(self):
        """Test main function with successful execution."""
        from agent import main
        from unittest.mock import patch, MagicMock
        import io
        import sys

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Test answer',
                    'tool_calls': []
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200

        with patch('sys.argv', ['agent.py', 'Test question?']):
            with patch('agent.load_config') as mock_load:
                mock_load.return_value = {
                    'api_key': 'test-key',
                    'api_base': 'https://test.api/v1',
                    'model': 'test-model'
                }
                with patch('agent.requests.post') as mock_post:
                    mock_post.return_value = mock_response

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
        mock_response_with_tool.json.return_value = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {
                            'name': 'read_file',
                            'arguments': '{"path": "wiki/git-workflow.md"}'
                        }
                    }]
                }
            }]
        }
        mock_response_with_tool.raise_for_status = MagicMock()

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'To resolve merge conflicts, see wiki/git-workflow.md#resolving-merge-conflicts',
                    'tool_calls': []
                }
            }]
        }
        mock_response_final.raise_for_status = MagicMock()

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model'
        }

        with patch('agent.requests.post') as mock_post:
            # First call returns tool call, second returns final answer
            mock_post.side_effect = [
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
        mock_response_with_tool.json.return_value = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {
                            'name': 'list_files',
                            'arguments': '{"path": "wiki"}'
                        }
                    }]
                }
            }]
        }
        mock_response_with_tool.raise_for_status = MagicMock()

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'The wiki directory contains documentation files about Git, Docker, API, and more.',
                    'tool_calls': []
                }
            }]
        }
        mock_response_final.raise_for_status = MagicMock()

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model'
        }

        with patch('agent.requests.post') as mock_post:
            # First call returns tool call, second returns final answer
            mock_post.side_effect = [
                mock_response_with_tool,
                mock_response_final
            ]

            result = call_llm_with_tools("What files are in the wiki?", config)

            # Verify list_files was called
            assert len(result["tool_calls"]) >= 1
            assert any(tc["tool"] == "list_files" for tc in result["tool_calls"])

    def test_items_count_question_uses_query_api(self):
        """Test that a question about item count triggers query_api tool."""
        from agent import call_llm_with_tools
        from agent import _api_cache
        from unittest.mock import MagicMock, patch

        # Clear cache before test
        _api_cache.clear()

        # Mock LLM response that calls query_api tool
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "query_api"
        mock_tool_call.function.arguments = '{"method": "GET", "path": "/items/"}'
        mock_tool_call.id = "call_1"

        # First response: tool call
        mock_response_with_tool = MagicMock()
        mock_response_with_tool.json.return_value = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {
                            'name': 'query_api',
                            'arguments': '{"method": "GET", "path": "/items/"}'
                        }
                    }]
                }
            }]
        }
        mock_response_with_tool.raise_for_status = MagicMock()

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'The system contains 5 items as returned by the /items/ API endpoint.',
                    'tool_calls': []
                }
            }]
        }
        mock_response_final.raise_for_status = MagicMock()

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model',
            'api_base_url': 'http://localhost:42002',
            'lms_api_key': 'test-lms-key'
        }

        # Mock API response for query_api
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {"count": 5, "items": []}
        mock_api_response.status_code = 200
        mock_api_response.raise_for_status = MagicMock()

        with patch('agent.requests.request') as mock_request:
            mock_request.return_value = mock_api_response
            
            with patch('agent.requests.post') as mock_post:
                # First call returns tool call, second returns final answer
                mock_post.side_effect = [
                    mock_response_with_tool,
                    mock_response_final
                ]

                result = call_llm_with_tools("How many items are in the system?", config)

                # Verify query_api was called
                assert len(result["tool_calls"]) >= 1
                assert any(tc["tool"] == "query_api" for tc in result["tool_calls"])

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


class TestQueryApiTool:
    """Tests for the query_api tool."""

    def test_query_api_get_request(self):
        """Test query_api with GET request."""
        from agent import query_api, _api_cache
        from unittest.mock import patch

        # Clear cache
        _api_cache.clear()
        
        config = {
            'api_base_url': 'http://localhost:42002',
            'lms_api_key': 'test-key'
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch('agent.requests.request') as mock_request:
            mock_request.return_value = mock_response

            result = query_api("GET", "/items/", config=config)

            assert result["success"] is True
            assert result["data"] == {"data": "test"}
            mock_request.assert_called_once()

    def test_query_api_auth_header(self):
        """Test that query_api includes Authorization Bearer header."""
        from agent import query_api, _api_cache
        from unittest.mock import patch

        # Clear cache
        _api_cache.clear()
        
        config = {
            'api_base_url': 'http://localhost:42002',
            'lms_api_key': 'secret-key-123'
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.status_code = 200

        with patch('agent.requests.request') as mock_request:
            mock_request.return_value = mock_response

            query_api("GET", "/items/", config=config)

            # Verify headers include Authorization Bearer
            call_args = mock_request.call_args
            headers = call_args[1]['headers']
            assert headers["Authorization"] == "Bearer secret-key-123"

    def test_query_api_rate_limit_retry(self):
        """Test that query_api retries on 429 rate limit."""
        from agent import query_api, _api_cache
        from unittest.mock import patch

        # Clear cache
        _api_cache.clear()
        
        config = {
            'api_base_url': 'http://localhost:42002',
            'lms_api_key': 'test-key'
        }

        # First two calls return 429, third succeeds
        mock_429 = MagicMock()
        mock_429.status_code = 429

        mock_success = MagicMock()
        mock_success.json.return_value = {"data": "success"}
        mock_success.status_code = 200

        with patch('agent.requests.request') as mock_request:
            mock_request.side_effect = [mock_429, mock_429, mock_success]

            with patch('agent.time.sleep'):  # Skip actual sleep
                result = query_api("GET", "/items/", config=config)

            assert result["success"] is True
            assert mock_request.call_count == 3

    def test_query_api_invalid_method(self):
        """Test query_api with invalid HTTP method."""
        from agent import query_api

        result = query_api("PATCH", "/items/")

        assert result["success"] is False
        assert "Invalid method" in result["error"]

    def test_query_api_connection_error(self):
        """Test query_api handles connection errors."""
        from agent import query_api, _api_cache
        from unittest.mock import patch
        import requests

        # Clear cache to ensure fresh request
        _api_cache.clear()

        config = {
            'api_base_url': 'http://localhost:42002',
            'lms_api_key': 'test-key'
        }

        with patch('agent.requests.request') as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

            result = query_api("GET", "/items/", config=config)

            assert result["success"] is False
            assert "Connection error" in result["error"]


class TestSystemAgentRegression:
    """Regression tests for System Agent (Task 3) - query_api tool."""

    def test_framework_question_uses_read_file(self):
        """Test that 'What framework does the backend use?' triggers read_file tool."""
        from agent import call_llm_with_tools
        from unittest.mock import MagicMock, patch

        # Mock LLM response that calls read_file tool for backend source code
        mock_response_with_tool = MagicMock()
        mock_response_with_tool.json.return_value = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {
                            'name': 'read_file',
                            'arguments': '{"path": "backend/main.py"}'
                        }
                    }]
                }
            }]
        }
        mock_response_with_tool.raise_for_status = MagicMock()

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'The backend uses FastAPI framework as seen in backend/main.py',
                    'tool_calls': []
                }
            }]
        }
        mock_response_final.raise_for_status = MagicMock()

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model'
        }

        with patch('agent.requests.post') as mock_post:
            mock_post.side_effect = [
                mock_response_with_tool,
                mock_response_final
            ]

            result = call_llm_with_tools("What Python web framework does this project's backend use?", config)

            # Verify read_file was called (not query_api)
            assert len(result["tool_calls"]) >= 1
            assert any(tc["tool"] == "read_file" for tc in result["tool_calls"])
            assert not any(tc["tool"] == "query_api" for tc in result["tool_calls"])

    def test_items_count_question_uses_query_api(self):
        """Test that 'How many items are in the database?' triggers query_api tool."""
        from agent import call_llm_with_tools
        from agent import _api_cache
        from unittest.mock import MagicMock, patch

        # Clear cache before test
        _api_cache.clear()

        # Mock LLM response that calls query_api tool
        mock_response_with_tool = MagicMock()
        mock_response_with_tool.json.return_value = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {
                            'name': 'query_api',
                            'arguments': '{"method": "GET", "path": "/items/"}'
                        }
                    }]
                }
            }]
        }
        mock_response_with_tool.raise_for_status = MagicMock()

        # Second response: final answer
        mock_response_final = MagicMock()
        mock_response_final.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'There are 42 items in the database as returned by GET /items/',
                    'tool_calls': []
                }
            }]
        }
        mock_response_final.raise_for_status = MagicMock()

        config = {
            'api_key': 'test-key',
            'api_base': 'https://test.api/v1',
            'model': 'test-model',
            'api_base_url': 'http://localhost:42002',
            'lms_api_key': 'test-lms-key'
        }

        # Mock API response for query_api
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {"count": 42, "items": []}
        mock_api_response.status_code = 200
        mock_api_response.raise_for_status = MagicMock()

        with patch('agent.requests.request') as mock_request:
            mock_request.return_value = mock_api_response

            with patch('agent.requests.post') as mock_post:
                mock_post.side_effect = [
                    mock_response_with_tool,
                    mock_response_final
                ]

                result = call_llm_with_tools("How many items are in the database?", config)

                # Verify query_api was called (not read_file)
                assert len(result["tool_calls"]) >= 1
                assert any(tc["tool"] == "query_api" for tc in result["tool_calls"])
                assert not any(tc["tool"] == "read_file" for tc in result["tool_calls"])
