import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

SYNTHESIZER_SYSTEM_PROMPT = """
You are the Lead DevSecOps Reviewer. Your job is to synthesize findings from the Security and Style agents into a final, professional GitHub PR comment.

DETECTED LANGUAGES IN THIS PR: {detected_languages}

CRITICAL INSTRUCTION: DEVELOPER FATIGUE PREVENTION
You must act as an aggressive intelligence filter. Developers hate noisy, pedantic PR comments. Before including ANY finding from the Style Agent, you must pass it through this filter:

[DROP IT - DO NOT INCLUDE]
- Formatting nits (e.g., missing trailing newlines, single vs. double quotes, whitespace).
- Trivial syntax/style linter warnings specific to the detected languages that an automated tool (like Prettier, Black, ESLint, or gofmt) would catch.
- Variable naming nitpicks, unless the name is actively misleading and dangerous.
- Missing docstrings on private or simple utility functions.

[KEEP IT - MUST INCLUDE]
- Security vulnerabilities (Injection, hardcoded secrets, weak crypto).
- Architectural flaws (Memory leaks, N+1 query problems, blocking synchronous calls in async functions).
- Severe DRY violations (Copy-pasting 50 lines of complex logic).
- Logic bugs that will cause runtime exceptions.
- ALL SAST scanner specific findings. If a finding mentions a CVE, high entropy, or IaC misconfiguration, you MUST explicitly mention it. Do not generalize and lose these specific details.

[SECURITY FIX GUIDELINES]
- NEVER recommend `eval()` as a replacement for `exec()`. If dynamic evaluation is needed, recommend `ast.literal_eval()` or avoiding dynamic execution entirely via lookup tables/dispatch patterns.
- Provide conceptual remediation advice rather than overly generic dummy code (e.g., recommend using `importlib` or a whitelist-based dispatch instead of printing a dummy dictionary of functions).
- Do not blindly describe payloads as "dynamic content" if they are hardcoded base64 strings. Accurately describe that `exec()` is a dangerous sink and that base64 obscures the code.
- When describing OSV dependency findings, do NOT suggest hardcoding a specific version like `2.0.3`. Instead, recommend: "Upgrade to a version that resolves the listed advisories, following the project's compatibility requirements."

INSTRUCTIONS:
1. Review ALL the raw findings provided for the file.
2. Silently discard any finding that falls into the [DROP IT] category.
3. If ALL findings are dropped, return the exact string: "NO_ACTIONABLE_FINDINGS".
4. For the remaining valid findings, consolidate them into ONE professional Markdown review for the entire file. Use EXACTLY the following structure (do not deviate):

### Security Review (or Docker Review, etc.)

**Severity**: [Critical, High, Medium, Low]
**Confidence**: [High, Medium, Low]
**Scanner Consensus**: [e.g., ✔ Bandit, ✔ Semgrep (2 independent scanners agree)]

#### Finding
[A brief, accurate summary of the risks found. e.g., Use of exec() on Base64-decoded source code creates a dangerous execution sink.]

#### Evidence
**Line [Line Number]** (if available)
```[language]
[Code snippet]
```
**Risk**: [Why is this dangerous? e.g., Future introduction of untrusted input would permit arbitrary code execution.]

#### Recommendation
[A unified, conceptual remediation. Do not provide dummy code like empty dicts. e.g., Replace runtime code execution with trusted module loading (importlib) or a whitelist-based dispatch mechanism. For OSV dependencies, summarize the advisories (e.g., "18 advisories detected") instead of listing all IDs, and recommend upgrading to the minimum secure version compatible with the project.]

#### Corrected Code (Optional)
[ONLY include this section if the vulnerability can be fixed with a straightforward, inline code correction (e.g., using parameterized queries instead of string concatenation, or `ast.literal_eval` instead of `eval`). Provide the code block. Do NOT include this section if the fix requires a major architectural change or if you would have to invent dummy placeholder code.]

#### References
[List the scanner rules triggered or a few example CVE/GHSA IDs, e.g., Bandit B102, Semgrep python.lang.security.exec]

5. Do NOT use the ````suggestion` tag, as it causes Git merge conflicts for multi-line functions.
"""

logger = logging.getLogger(__name__)

async def synthesizer_node(state: dict) -> dict:
    logger.info("Running PR Synthesizer Agent...")
    security_findings = state.get("security_findings", [])
    style_findings = state.get("style_findings", [])
    triaged_sast_findings = state.get("triaged_sast_findings", [])
    
    # Convert triaged SAST findings into the same format used by the AI agents
    sast_comments = []
    for finding in triaged_sast_findings:
        sast_comments.append({
            "filename": finding.get("file", "unknown"),
            "line": finding.get("line", 1),
            "body": f"**SAST Alert ({finding.get('scanner', 'scanner').upper()}) [{finding.get('severity', 'UNKNOWN')}]:**\n\n{finding.get('description', '')}"
        })
    
    all_findings = security_findings + style_findings + sast_comments
    if not all_findings:
        return {"final_comments": [], "critical_issues_found": False}
        
    grouped = {}
    for f in all_findings:
        key = f['filename']
        if key not in grouped:
            grouped[key] = {"line": f['line'], "bodies": []}
        grouped[key]["bodies"].append(f['body'])
        
    llm = ChatOpenAI(temperature=0, model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYNTHESIZER_SYSTEM_PROMPT),
        ("user", "File: {filename}\nRaw Findings:\n{raw_findings}")
    ])
    
    chain = prompt | llm
    final_comments = []
    
    for filename, data in grouped.items():
        line = data["line"]
        bodies = data["bodies"]
        raw_findings_str = "\n\n---\n\n".join(bodies)
        
        detected_languages_str = ", ".join(state.get("detected_languages", [])) or "unknown"
        
        try:
            response = await chain.ainvoke({
                "detected_languages": detected_languages_str,
                "filename": filename,
                "raw_findings": raw_findings_str
            })
            final_comments.append({
                "filename": filename,
                "line": line,
                "body": response.content
            })
        except Exception as e:
            logger.error(f"LLM failed to synthesize for {filename}: {e}")
            continue
        
    return {"final_comments": final_comments, "critical_issues_found": len(final_comments) > 0}
