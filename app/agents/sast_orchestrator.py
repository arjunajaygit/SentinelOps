import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

SAST_TRIAGE_SYSTEM_PROMPT = """
You are a Senior Security Triage Analyst working inside a DevSecOps CI pipeline.
You have been given a list of raw alerts from traditional SAST scanners (Bandit, Semgrep, Gitleaks).

Your job is to analyze each alert and determine if it is a TRUE POSITIVE or a FALSE POSITIVE.

CLASSIFY AS FALSE POSITIVE (DROP SILENTLY):
- Alerts in test files (e.g., test_*.py, *_test.go, *.spec.ts).
- Alerts on example/placeholder code, documentation, or comments.
- Hardcoded strings that are obviously NOT secrets (e.g., "localhost", "example.com", placeholder UUIDs).
- Low-severity informational warnings with no real exploit path.
- Alerts on code that is properly sanitized or uses parameterized queries.

CLASSIFY AS TRUE POSITIVE (KEEP):
- Hardcoded API keys, passwords, or tokens that appear to be real credentials.
- SQL injection, command injection, or path traversal vulnerabilities.
- Use of weak cryptographic algorithms (MD5, SHA1 for security, DES).
- Sensitive data exposure (logging secrets, returning credentials in API responses).
- Dependency vulnerabilities (e.g., OSV Scanner results, CVEs).
- Infrastructure as Code (IaC) or Docker misconfigurations (Checkov, Hadolint).
- Custom EntropyGuard findings (high entropy or obfuscated payloads).
- Any HIGH or CRITICAL severity finding that has a plausible exploit path.

INSTRUCTIONS:
1. Read the JSON list of alerts below.
2. For each alert, output your verdict.
3. Return ONLY a valid JSON array of the TRUE POSITIVE alerts. Each object must have: "scanner", "severity", "file", "line", "description".
4. If ALL alerts are false positives, return an empty JSON array: []
5. Do NOT add any commentary, markdown formatting, or explanation outside the JSON array.
"""

logger = logging.getLogger(__name__)


async def sast_orchestrator_node(state: dict) -> dict:
    """
    LangGraph node that triages raw SAST alerts using an LLM to filter out false positives.
    """
    logger.info("Running SAST Orchestrator (Alert Triage Analyst)...")

    raw_alerts = state.get("raw_sast_alerts", [])

    if not raw_alerts:
        logger.info("No raw SAST alerts to triage. Skipping.")
        return {"triaged_sast_findings": []}

    llm = ChatOpenAI(
        temperature=0,
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SAST_TRIAGE_SYSTEM_PROMPT),
        ("user", "Raw SAST Alerts ({alert_count} total):\n```json\n{alerts_json}\n```")
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "alert_count": len(raw_alerts),
            "alerts_json": json.dumps(raw_alerts, indent=2)
        })

        content = response.content.strip()

        # Strip any markdown code fences the LLM might add
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        triaged = json.loads(content)

        if not isinstance(triaged, list):
            logger.warning("LLM returned non-list response for SAST triage. Discarding.")
            triaged = []

        logger.info(f"SAST Triage complete: {len(triaged)} true positives out of {len(raw_alerts)} raw alerts.")
        return {"triaged_sast_findings": triaged}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM triage response as JSON: {e}")
        # Graceful degradation: pass through all raw alerts if the LLM fails to parse
        logger.warning("Falling back to passing all raw alerts as true positives.")
        return {"triaged_sast_findings": raw_alerts}
    except Exception as e:
        logger.error(f"SAST Orchestrator failed: {e}")
        return {"triaged_sast_findings": []}
