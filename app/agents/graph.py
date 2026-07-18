import operator
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END, START
from app.agents.security_agent import security_node
from app.agents.style_agent import style_node
from app.agents.sast_orchestrator import sast_orchestrator_node
from app.agents.synthesizer import synthesizer_node

class AgentState(TypedDict):
    repo_full_name: str
    pr_number: int
    commit_id: str
    diff_data: List[Dict[str, Any]]
    dependent_files: List[str]
    chroma_persist_dir: str
    detected_languages: List[str]
    
    # We use operator.add to append to lists so parallel nodes merge rather than overwrite.
    security_findings: Annotated[List[Dict[str, Any]], operator.add]
    style_findings: Annotated[List[Dict[str, Any]], operator.add]
    
    # SAST Orchestrator state
    raw_sast_alerts: List[Dict[str, Any]]
    triaged_sast_findings: List[Dict[str, Any]]
    
    final_comments: List[Dict[str, Any]]
    critical_issues_found: bool

def build_graph():
    """
    Builds the LangGraph workflow for SentinelOps.
    Security, Style, and SAST Orchestrator run in parallel (fan-out),
    then converge into the Synthesizer (fan-in).
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("security", security_node)
    workflow.add_node("style", style_node)
    workflow.add_node("sast_orchestrator", sast_orchestrator_node)
    workflow.add_node("synthesizer", synthesizer_node)
    
    # Fan-out: all three analysis nodes start from START in parallel
    workflow.add_edge(START, "security")
    workflow.add_edge(START, "style")
    workflow.add_edge(START, "sast_orchestrator")
    
    # Fan-in: all three converge into synthesizer
    workflow.add_edge("security", "synthesizer")
    workflow.add_edge("style", "synthesizer")
    workflow.add_edge("sast_orchestrator", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile()
