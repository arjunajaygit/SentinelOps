import logging
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.rag.retriever import CodebaseRetriever
from app.utils.diff_parser import parse_file_patch, extract_added_lines

logger = logging.getLogger(__name__)

async def style_node(state: dict) -> dict:
    logger.info("Running Style Agent...")
    diff_data = state.get("diff_data", [])
    persist_dir = state.get("chroma_persist_dir")
    
    if not persist_dir:
        logger.warning("No chroma_persist_dir found in state.")
        return {"style_findings": []}
        
    retriever = CodebaseRetriever(persist_dir)
    llm = ChatGroq(temperature=0, model="llama-3.3-70b-versatile", api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict Code Style Specialist Agent.
Your job is to analyze code additions for maintainability, technical debt, DRY violations, and language-specific anti-patterns.
You are provided with the diff of the file and some context from the broader codebase.
If you find a style or maintainability issue, output exactly what needs to change. Include a code snippet with the correction so the Synthesizer can generate a GitHub suggestion block.
If the code looks good, respond with "NO_ISSUE" exactly.
"""),
        ("user", "File: {filename}\n\nCodebase Context:\n{context}\n\nDiff Patch:\n{patch}")
    ])
    
    chain = prompt | llm
    findings = []
    
    for file in diff_data:
        filename = file['filename']
        patch = file['patch']
        
        hunks = parse_file_patch(patch)
        added_lines = extract_added_lines(hunks)
        
        if not added_lines:
            continue
            
        context = await retriever.aget_context_for_code(patch)
        
        response = await chain.ainvoke({
            "filename": filename,
            "context": context,
            "patch": patch
        })
        
        content = response.content.strip()
        if content != "NO_ISSUE":
            target_line = added_lines[0]['line_number']
            findings.append({
                "filename": filename,
                "line": target_line,
                "body": f"**Code Style Analysis:**\n\n{content}"
            })
            
    return {"style_findings": findings}
