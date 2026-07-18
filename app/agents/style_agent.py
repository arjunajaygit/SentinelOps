import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.rag.retriever import CodebaseRetriever
from app.utils.diff_parser import parse_file_patch, extract_added_lines

logger = logging.getLogger(__name__)

async def style_node(state: dict) -> dict:
    logger.info("Running Style Agent...")
    diff_data = state.get("diff_data", [])
    dependent_files = state.get("dependent_files", [])
    persist_dir = state.get("chroma_persist_dir")
    
    if not persist_dir:
        logger.warning("No chroma_persist_dir found in state.")
        return {"style_findings": []}
        
    retriever = CodebaseRetriever(persist_dir)
    llm = ChatOpenAI(temperature=0, model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict Code Style Specialist Agent.
Your job is to analyze code additions for maintainability, technical debt, DRY violations, and language-specific anti-patterns.
You are provided with the diff of the file and some context from the broader codebase.

You are also evaluating Blast Radius. If the developer changed a function signature, return type, or core assumption in the PR, check the provided RAG context to see if dependent files rely on the old behavior. If a breaking change is detected, flag it as an architectural flaw. DO NOT review the dependent files for their own independent security/style issues.

If you find a style or maintainability issue, output exactly what needs to change. Include a code snippet with the correction so the Synthesizer can generate a GitHub suggestion block.
If the code looks good, respond with "NO_ISSUE" exactly.
"""),
        ("user", "File: {filename}\n\nCodebase Context:\n{context}\n\nDiff Patch:\n{patch}")
    ])
    
    chain = prompt | llm
    
    findings = []
    for file_data in diff_data:
        filename = file_data.get('filename')
        patch = file_data.get('patch')
        
        if not patch:
            continue
            
        hunks = parse_file_patch(patch)
        added_lines = extract_added_lines(hunks)
        
        # Get added/modified lines for context targeting source code file (e.g. README.md)
        if not filename.endswith(('.py', '.js', '.ts', '.go', '.java', '.c', '.cpp', '.rb', '.php', '.sh')):
            continue
            
        if not added_lines:
            continue
            
        context = await retriever.aget_context_for_code(patch, filename=filename, dependent_files=dependent_files)
        
        try:
            response = await chain.ainvoke({
                "filename": filename,
                "patch": patch,
                "context": context
            })
            content = response.content.strip()
            if content != "NO_ISSUE":
                findings.append({
                    "filename": filename,
                    "line": 1,
                    "body": f"**Code Style Analysis**\n\n{content}"
                })
        except Exception as e:
            logger.error(f"LLM failed to analyze style for {filename}: {e}")
            continue
            
    return {"style_findings": findings}
