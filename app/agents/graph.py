import operator
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from app.agents.security_agent import security_node
from app.agents.style_agent import style_node
from app.agents.synthesizer import synthesizer_node

class AgentState(TypedDict):
    repo_full_name: str
    pr_number: int
    commit_id: str
    diff_data: List[Dict[str, Any]]
    chroma_persist_dir: str
    
    # We use operator.add to append to lists rather than overwrite them if we run nodes in parallel,
    # but for simplicity we will run them sequentially. It's still good practice to annotate for appending.
    security_findings: Annotated[List[Dict[str, Any]], operator.add]
    style_findings: Annotated[List[Dict[str, Any]], operator.add]
    
    final_comments: List[Dict[str, Any]]

def build_graph():
    """
    Builds the LangGraph workflow for SentinelOps.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("security", security_node)
    workflow.add_node("style", style_node)
    workflow.add_node("synthesizer", synthesizer_node)
    
    # Define execution graph (sequential for simplicity)
    workflow.set_entry_point("security")
    workflow.add_edge("security", "style")
    workflow.add_edge("style", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile()
