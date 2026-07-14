import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_webhook_invalid_signature():
    """Ensure a request with an invalid signature is rejected with a 401."""
    # Temporarily force a webhook secret for this test
    original_secret = settings.WEBHOOK_SECRET
    settings.WEBHOOK_SECRET = "strict_secret"
    
    response = client.post(
        "/webhook",
        json={"action": "opened"},
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=invalid_signature_here"
        }
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"
    
    settings.WEBHOOK_SECRET = original_secret

@patch("app.main.process_pull_request")
def test_webhook_valid_signature(mock_process, valid_signature):
    """Ensure a valid request returns 200/202 and queues the background task."""
    signature, payload_bytes = valid_signature
    
    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature
        }
    )
    
    assert response.status_code == 200
    assert response.json()["msg"] == "Processing Pull Request in background"
    # Verify the background task was dispatched
    assert mock_process.called
