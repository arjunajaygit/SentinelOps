import logging
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

SYNTHESIZER_SYSTEM_PROMPT = """
You are the Lead DevSecOps Reviewer. Your job is to synthesize findings from the Security and Style agents into a final, professional GitHub PR comment.

CRITICAL INSTRUCTION: DEVELOPER FATIGUE PREVENTION
You must act as an aggressive intelligence filter. Developers hate noisy, pedantic PR comments. Before including ANY finding from the Style Agent, you must pass it through this filter:

[DROP IT - DO NOT INCLUDE]
- Formatting nits (e.g., missing trailing newlines, single vs. double quotes, whitespace).
- Trivial PEP8/Linter warnings that an automated tool (like Ruff, Flake8, or Black) would catch.
- Variable naming nitpicks, unless the name is actively misleading and dangerous.
- Missing docstrings on private or simple utility functions.

[KEEP IT - MUST INCLUDE]
- Security vulnerabilities (Injection, hardcoded secrets, weak crypto).
- Architectural flaws (Memory leaks, N+1 query problems, blocking synchronous calls in async functions).
- Severe DRY violations (Copy-pasting 50 lines of complex logic).
- Logic bugs that will cause runtime exceptions.

INSTRUCTIONS:
1. Review the input findings. 
2. Silently discard any finding that falls into the [DROP IT] category.
3. If ALL findings are dropped, return the exact string: "NO_ACTIONABLE_FINDINGS".
4. For the remaining valid findings, format them as a professional Markdown review, including a ```suggestion``` block with the exact diff to fix the issue.
"""

logger = logging.getLogger(__name__)

async def synthesizer_node(state: dict) -> dict:
    logger.info("Running PR Synthesizer Agent...")
    security_findings = state.get("security_findings", [])
    style_findings = state.get("style_findings", [])
    
    all_findings = security_findings + style_findings
    if not all_findings:
        return {"final_comments": []}
        
    grouped = {}
    for f in all_findings:
        key = (f['filename'], f['line'])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(f['body'])
        
    llm = ChatGroq(temperature=0, model="llama-3.3-70b-versatile", api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYNTHESIZER_SYSTEM_PROMPT),
        ("user", "File: {filename}, Line: {line}\nRaw Findings:\n{raw_findings}")
    ])
    
    chain = prompt | llm
    final_comments = []
    
    for (filename, line), bodies in grouped.items():
        raw_findings_str = "\n\n---\n\n".join(bodies)
        response = await chain.ainvoke({
            "filename": filename,
            "line": line,
            "raw_findings": raw_findings_str
        })
        
        final_comments.append({
            "filename": filename,
            "line": line,
            "body": response.content
        })
        
    return {"final_comments": final_comments}
