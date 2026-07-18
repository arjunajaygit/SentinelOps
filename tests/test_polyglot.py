import os
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.utils.sast_runner import detect_languages, run_all_sast_scanners
from app.rag.indexer import CodebaseIndexer
from langchain_text_splitters import Language

@pytest.fixture
def mock_subprocess():
    """Mock asyncio.create_subprocess_exec to prevent actual tool execution."""
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        # Mock the process object returned by create_subprocess_exec
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'{"results": []}', b"")
        mock_exec.return_value = mock_process
        yield mock_exec

def test_detect_languages(tmp_path):
    """
    Test that language detection correctly identifies languages based on extensions
    and ignores files in specified ignore directories.
    """
    # Create valid files
    (tmp_path / "main.py").touch()
    (tmp_path / "app.js").touch()
    (tmp_path / "backend.go").touch()
    (tmp_path / "extra.ts").touch() # Should also be detected as javascript
    
    # Create ignored directories and files inside them
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "test.js").touch()
    (node_modules / "bad.go").touch()
    
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "script.py").touch()
    
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hook.py").touch()
    
    (tmp_path / "main.tf").touch()
    (tmp_path / "Dockerfile").touch()
    
    languages = set(detect_languages(str(tmp_path)))
    
    # Assert correct languages are found and ignored directories are skipped
    assert "python" in languages
    assert "javascript" in languages
    assert "go" in languages
    assert "terraform" in languages
    assert "docker" in languages
    assert len(languages) == 5


@pytest.mark.asyncio
@patch("app.utils.sast_runner.detect_languages")
async def test_dynamic_sast_routing_python_only(mock_detect, mock_subprocess):
    """
    Test SAST routing when only Python is detected.
    Should run: bandit, semgrep, gitleaks.
    Should NOT run: njsscan, gosec.
    """
    mock_detect.return_value = ["python"]
    
    with patch("app.utils.sast_runner.run_bandit", new_callable=AsyncMock) as mock_bandit, \
         patch("app.utils.sast_runner.run_njsscan", new_callable=AsyncMock) as mock_njsscan, \
         patch("app.utils.sast_runner.run_gosec", new_callable=AsyncMock) as mock_gosec, \
         patch("app.utils.sast_runner.run_semgrep", new_callable=AsyncMock) as mock_semgrep, \
         patch("app.utils.sast_runner.run_secrets_scan", new_callable=AsyncMock) as mock_secrets:
             
        mock_bandit.return_value = []
        mock_semgrep.return_value = []
        mock_secrets.return_value = []
        
        with patch("app.utils.sast_runner.run_osv_scan", new_callable=AsyncMock) as mock_osv, \
             patch("app.utils.sast_runner.run_entropy_scan", new_callable=AsyncMock) as mock_entropy:
            mock_osv.return_value = []
            mock_entropy.return_value = []
            await run_all_sast_scanners("/dummy/path", [])
        
        # Always run
        mock_semgrep.assert_called_once()
        mock_secrets.assert_called_once()
        
        # Conditionally run
        mock_bandit.assert_called_once()
        mock_njsscan.assert_not_called()
        mock_gosec.assert_not_called()


@pytest.mark.asyncio
@patch("app.utils.sast_runner.detect_languages")
async def test_dynamic_sast_routing_js_and_go(mock_detect, mock_subprocess):
    """
    Test SAST routing when Javascript and Go are detected.
    Should run: njsscan, gosec, semgrep, gitleaks.
    Should NOT run: bandit.
    """
    mock_detect.return_value = ["javascript", "go"]
    
    with patch("app.utils.sast_runner.run_bandit", new_callable=AsyncMock) as mock_bandit, \
         patch("app.utils.sast_runner.run_njsscan", new_callable=AsyncMock) as mock_njsscan, \
         patch("app.utils.sast_runner.run_gosec", new_callable=AsyncMock) as mock_gosec, \
         patch("app.utils.sast_runner.run_semgrep", new_callable=AsyncMock) as mock_semgrep, \
         patch("app.utils.sast_runner.run_secrets_scan", new_callable=AsyncMock) as mock_secrets:
             
        mock_njsscan.return_value = []
        mock_gosec.return_value = []
        mock_semgrep.return_value = []
        mock_secrets.return_value = []
        
        with patch("app.utils.sast_runner.run_osv_scan", new_callable=AsyncMock) as mock_osv, \
             patch("app.utils.sast_runner.run_entropy_scan", new_callable=AsyncMock) as mock_entropy:
            mock_osv.return_value = []
            mock_entropy.return_value = []
            await run_all_sast_scanners("/dummy/path", [])
        
        # Always run
        mock_semgrep.assert_called_once()
        mock_secrets.assert_called_once()
        
        # Conditionally run
        mock_njsscan.assert_called_once()
        mock_gosec.assert_called_once()
        mock_bandit.assert_not_called()


@patch("app.rag.indexer.Chroma")
@patch("app.rag.indexer.TextLoader")
@patch("app.rag.indexer.RecursiveCharacterTextSplitter.from_language")
def test_indexer_language_mapping(mock_splitter_from_lang, mock_text_loader, mock_chroma, tmp_path):
    """
    Test that Polyglot RAG maps file extensions to correct LangChain Language enums.
    """
    # Create the dummy files so `os.path.isfile` returns True
    diff_files = ["utils.py", "frontend.js", "api.go"]
    for file in diff_files:
        (tmp_path / file).touch()
        
    # Setup mock text loader to return a dummy document
    mock_loader_instance = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {}
    mock_loader_instance.load.return_value = [mock_doc]
    mock_text_loader.return_value = mock_loader_instance
    
    # Setup mock splitter
    mock_splitter_instance = MagicMock()
    mock_splitter_instance.split_documents.return_value = [mock_doc]
    mock_splitter_from_lang.return_value = mock_splitter_instance

    indexer = CodebaseIndexer(repo_path=str(tmp_path), diff_files=diff_files)
    indexer.index_repository()
    
    # Assert the correct language enums were passed to the splitter
    calls = mock_splitter_from_lang.call_args_list
    assert len(calls) == 3
    
    called_languages = [call.kwargs.get("language") for call in calls]
    assert Language.PYTHON in called_languages
    assert Language.JS in called_languages
    assert Language.GO in called_languages


@patch("app.rag.indexer.Chroma")
@patch("app.rag.indexer.TextLoader")
def test_selective_indexing(mock_text_loader, mock_chroma, tmp_path):
    """
    Test that the CodebaseIndexer only processes the files specified in diff_files (Timeout Guard).
    """
    # Create 10 dummy files in the mock repository
    all_files = [f"file_{i}.py" for i in range(10)]
    for file in all_files:
        (tmp_path / file).touch()
        
    # Provide only 2 files in diff_files
    diff_files = ["file_2.py", "file_7.py"]
    
    # Setup mock text loader
    mock_loader_instance = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {}
    mock_loader_instance.load.return_value = [mock_doc]
    mock_text_loader.return_value = mock_loader_instance
    
    # Setup Chroma mock
    mock_chroma.from_documents = MagicMock()
    
    indexer = CodebaseIndexer(repo_path=str(tmp_path), diff_files=diff_files)
    indexer.index_repository()
    
    # Assert TextLoader was only called for the 2 files in diff_files, not all 10
    assert mock_text_loader.call_count == 2
    
    # Verify the specific files were loaded
    loaded_files = [call.args[0] for call in mock_text_loader.call_args_list]
    assert str(tmp_path / "file_2.py") in loaded_files
    assert str(tmp_path / "file_7.py") in loaded_files
    assert str(tmp_path / "file_0.py") not in loaded_files

@pytest.mark.asyncio
@patch("app.utils.sast_runner.detect_languages")
async def test_dynamic_sast_routing_iac(mock_detect, mock_subprocess):
    """
    Test SAST routing when Docker and Terraform are detected.
    Should run: checkov, hadolint, semgrep, gitleaks.
    """
    mock_detect.return_value = ["docker", "terraform"]
    
    with patch("app.utils.sast_runner.run_checkov", new_callable=AsyncMock) as mock_checkov, \
         patch("app.utils.sast_runner.run_hadolint", new_callable=AsyncMock) as mock_hadolint, \
         patch("app.utils.sast_runner.run_semgrep", new_callable=AsyncMock) as mock_semgrep, \
         patch("app.utils.sast_runner.run_secrets_scan", new_callable=AsyncMock) as mock_secrets:
             
        mock_checkov.return_value = []
        mock_hadolint.return_value = []
        mock_semgrep.return_value = []
        mock_secrets.return_value = []
        
        with patch("app.utils.sast_runner.run_osv_scan", new_callable=AsyncMock) as mock_osv, \
             patch("app.utils.sast_runner.run_entropy_scan", new_callable=AsyncMock) as mock_entropy:
            mock_osv.return_value = []
            mock_entropy.return_value = []
            await run_all_sast_scanners("/dummy/path", [])
        
        mock_checkov.assert_called_once()
        mock_hadolint.assert_called_once()
        mock_semgrep.assert_called_once()

@pytest.mark.asyncio
async def test_entropy_analyzer(tmp_path):
    from app.utils.entropy_analyzer import run_entropy_scan
    
    # Create a dummy python file with a guaranteed high-entropy string (all unique chars) near a sink
    test_file = tmp_path / "test_entropy.py"
    test_file.write_text("exec('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^')")
    
    alerts = await run_entropy_scan(str(tmp_path), ["test_entropy.py"])
    
    assert len(alerts) == 1
    assert alerts[0]["scanner"] == "EntropyGuard"
    assert alerts[0]["severity"] == "CRITICAL"
    assert "High entropy" in alerts[0]["description"]

@pytest.mark.asyncio
async def test_osv_scanner_mocked(tmp_path):
    from app.utils.osv_scanner import run_osv_scan
    
    # Create a dummy requirements.txt
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("urllib3==1.25.10")
    
    with patch("aiohttp.ClientSession.post") as mock_post:
        # Mock the aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "results": [
                {"vulns": [{"id": "CVE-2021-33503", "summary": "urllib3 ReDoS vulnerability"}]}
            ]
        }
        # __aenter__ is needed for async with
        mock_response.__aenter__.return_value = mock_response
        mock_post.return_value = mock_response
        
        alerts = await run_osv_scan(str(tmp_path), ["requirements.txt"])
        
        assert len(alerts) == 1
        assert alerts[0]["scanner"] == "osv"
        assert alerts[0]["severity"] == "CRITICAL"
        assert "CVE-2021-33503" in alerts[0]["description"]
