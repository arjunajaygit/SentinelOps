import pytest
import hmac
import hashlib
import json
from app.core.config import settings

@pytest.fixture(autouse=True)
def set_dummy_env_vars(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy_llm_key")
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_github_token")
    settings.LLM_API_KEY = "dummy_llm_key"
    settings.GITHUB_TOKEN = "dummy_github_token"

@pytest.fixture
def mock_pr_payload():
    """Generates a valid GitHub PR webhook JSON payload."""
    return {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "head": {"sha": "abcdef1234567890"}
        },
        "repository": {
            "full_name": "test-owner/test-repo",
            "clone_url": "https://github.com/test-owner/test-repo.git"
        }
    }

@pytest.fixture
def valid_signature(mock_pr_payload):
    """
    Generates a valid HMAC-SHA256 signature for the mock payload 
    using a dummy WEBHOOK_SECRET.
    """
    original_secret = settings.WEBHOOK_SECRET
    settings.WEBHOOK_SECRET = "dummy_test_secret"
    
    payload_bytes = json.dumps(mock_pr_payload).encode('utf-8')
    mac = hmac.new(settings.WEBHOOK_SECRET.encode(), msg=payload_bytes, digestmod=hashlib.sha256)
    signature = "sha256=" + mac.hexdigest()
    
    yield signature, payload_bytes
    
    # Teardown: restore original secret
    settings.WEBHOOK_SECRET = original_secret
