import pytest
from unittest.mock import patch, AsyncMock
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from app.agents.graph import build_graph
from app.rag.retriever import CodebaseRetriever

@pytest.fixture
def mock_state():
    return {
        "repo_full_name": "test/repo",
        "pr_number": 1,
        "commit_id": "abc1234",
        "diff_data": [
            {
                "filename": "test.py",
                "patch": "@@ -1,1 +1,2 @@\n+print('hello')"
            }
        ],
        "chroma_persist_dir": "/tmp/chroma",
        "detected_languages": [],
        "security_findings": [],
        "style_findings": [],
        "raw_sast_alerts": [],
        "triaged_sast_findings": [],
        "final_comments": [],
        "critical_issues_found": False
    }

async def mock_llm_ainvoke(self, prompt_input, config=None, **kwargs):
    """Side effect to route LLM responses based on agent prompts."""
    prompt_str = str(prompt_input)
    if "Security Specialist" in prompt_str:
        return AIMessage(content="Hardcoded secret detected!")
    elif "Code Style" in prompt_str:
        return AIMessage(content="NO_ISSUE")
    else:
        # Synthesizer
        return AIMessage(content="```suggestion\nprint('hello world')\n```")

async def mock_retriever_aget(*args, **kwargs):
    return "mocked context from chromadb"

@pytest.mark.asyncio
@patch.object(ChatOpenAI, "ainvoke", new=mock_llm_ainvoke)
@patch.object(CodebaseRetriever, "aget_context_for_code", new=mock_retriever_aget)
async def test_langgraph_workflow(mock_state):
    """
    Tests the LangGraph workflow orchestrating Security, Style, and Synthesizer nodes.
    Mocks out LangChain LLM and ChromaDB retrieval globally for deterministic output.
    """
    # Execute Workflow
    workflow = build_graph()
    final_state = await workflow.ainvoke(mock_state)
    
    # Assertions
    # Security found an issue
    assert len(final_state["security_findings"]) == 1
    assert final_state["security_findings"][0]["filename"] == "test.py"
    assert final_state["security_findings"][0]["line"] == 1
    
    # Style found NO_ISSUE
    assert len(final_state["style_findings"]) == 0
    
    # Synthesizer compiled the findings
    assert len(final_state["final_comments"]) == 1
    assert "suggestion" in final_state["final_comments"][0]["body"]
    assert final_state["final_comments"][0]["filename"] == "test.py"

