import os
import asyncio
import json
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

SCANNER_TIMEOUT = 120  # seconds

def detect_languages(clone_dir: str) -> List[str]:
    """
    Crawls the repository and detects languages based on file extensions.
    Ignores common dependency and build directories.
    """
    languages = set()
    ignored_dirs = {"node_modules", "venv", ".git", "dist", "build", ".chroma_db", "vendor"}
    
    for root, dirs, files in os.walk(clone_dir):
        # Mutate dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
        
        for file in files:
            if file.endswith(".py"):
                languages.add("python")
            elif file.endswith((".js", ".ts", ".jsx", ".tsx")):
                languages.add("javascript")
            elif file.endswith(".go"):
                languages.add("go")
            elif file.endswith(".java"):
                languages.add("java")
                
    logger.info(f"Detected languages in repository: {languages}")
    return list(languages)


async def run_bandit(clone_dir: str) -> List[Dict[str, Any]]:
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "bandit", "-r", clone_dir, "-f", "json", "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SCANNER_TIMEOUT)

        if process.returncode not in (0, 1):
            logger.warning(f"Bandit exited with code {process.returncode}: {stderr.decode()[:200]}")
            return []

        if stdout:
            data = json.loads(stdout.decode())
            for result in data.get("results", []):
                alerts.append({
                    "scanner": "bandit",
                    "severity": result.get("issue_severity", "UNKNOWN").upper(),
                    "file": result.get("filename", ""),
                    "line": result.get("line_number", 0),
                    "description": f"[{result.get('test_id', '')}] {result.get('issue_text', '')}",
                    "confidence": result.get("issue_confidence", "UNKNOWN").upper()
                })
    except Exception as e:
        logger.error(f"Error running Bandit: {e}")
    return alerts


async def run_njsscan(clone_dir: str) -> List[Dict[str, Any]]:
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "njsscan", "--json", clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SCANNER_TIMEOUT)

        if stdout:
            data = json.loads(stdout.decode())
            if "nodejs" in data:
                for category, details in data["nodejs"].items():
                    # details contains "files" and "metadata"
                    metadata = details.get("metadata", {})
                    severity = metadata.get("severity", "HIGH").upper()
                    description = metadata.get("description", category)
                    
                    for file_info in details.get("files", []):
                        # njsscan sometimes uses "file_path", and gives match_lines [start, end]
                        file_path = file_info.get("file_path", "")
                        lines = file_info.get("match_lines", [0])
                        start_line = lines[0] if lines else 0
                        
                        alerts.append({
                            "scanner": "njsscan",
                            "severity": severity,
                            "file": file_path,
                            "line": start_line,
                            "description": f"[{category}] {description}",
                            "confidence": "HIGH"
                        })
    except Exception as e:
        logger.error(f"Error running njsscan: {e}")
    return alerts


async def run_gosec(clone_dir: str) -> List[Dict[str, Any]]:
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "gosec", "-fmt=json", "-out=/dev/stdout", "./...",
            cwd=clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SCANNER_TIMEOUT)

        if stdout:
            data = json.loads(stdout.decode())
            for issue in data.get("Issues", []):
                alerts.append({
                    "scanner": "gosec",
                    "severity": issue.get("severity", "UNKNOWN").upper(),
                    "file": os.path.join(clone_dir, issue.get("file", "")), # gosec uses relative paths sometimes
                    "line": int(issue.get("line", "0").split("-")[0]), # gosec line can be a range like '15-18'
                    "description": f"[{issue.get('rule_id', '')}] {issue.get('details', '')}",
                    "confidence": issue.get("confidence", "UNKNOWN").upper()
                })
    except Exception as e:
        logger.error(f"Error running gosec: {e}")
    return alerts


async def run_semgrep(clone_dir: str) -> List[Dict[str, Any]]:
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "semgrep", "scan", "--json", "--quiet", clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SCANNER_TIMEOUT)

        if stdout:
            data = json.loads(stdout.decode())
            for result in data.get("results", []):
                alerts.append({
                    "scanner": "semgrep",
                    "severity": result.get("extra", {}).get("severity", "UNKNOWN").upper(),
                    "file": result.get("path", ""),
                    "line": result.get("start", {}).get("line", 0),
                    "description": f"[{result.get('check_id', '')}] {result.get('extra', {}).get('message', '')}",
                    "confidence": "HIGH"
                })
    except Exception as e:
        logger.error(f"Error running Semgrep: {e}")
    return alerts


async def run_secrets_scan(clone_dir: str) -> List[Dict[str, Any]]:
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "gitleaks", "detect", "--source", clone_dir,
            "--report-format", "json", "--report-path", "/dev/stdout",
            "--no-git",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SCANNER_TIMEOUT)

        if stdout:
            data = json.loads(stdout.decode())
            if isinstance(data, list):
                for leak in data:
                    alerts.append({
                        "scanner": "gitleaks",
                        "severity": "CRITICAL",
                        "file": leak.get("File", ""),
                        "line": leak.get("StartLine", 0),
                        "description": f"[{leak.get('RuleID', 'secret')}] Secret detected: {leak.get('Description', 'Potential secret or credential')}",
                        "confidence": "HIGH"
                    })
    except Exception as e:
        logger.error(f"Error running Gitleaks: {e}")
    return alerts


async def run_all_sast_scanners(clone_dir: str) -> Dict[str, Any]:
    """
    Detects languages, dynamically allocates SAST tools, and runs them concurrently.
    Returns a unified dict containing detected languages and normalized alerts.
    """
    logger.info(f"Starting concurrent SAST scans on: {clone_dir}")
    
    detected_languages = detect_languages(clone_dir)
    
    # Always run Semgrep and Gitleaks
    tasks = {
        "semgrep": run_semgrep(clone_dir),
        "gitleaks": run_secrets_scan(clone_dir)
    }
    
    # Dynamically allocate language-specific scanners
    if "python" in detected_languages:
        tasks["bandit"] = run_bandit(clone_dir)
    if "javascript" in detected_languages:
        tasks["njsscan"] = run_njsscan(clone_dir)
    if "go" in detected_languages:
        tasks["gosec"] = run_gosec(clone_dir)
        
    scanner_names = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    
    aggregated = []
    for scanner_name, result in zip(scanner_names, results):
        if isinstance(result, Exception):
            logger.error(f"SAST scanner '{scanner_name}' raised an exception: {result}")
        elif isinstance(result, list):
            aggregated.extend(result)

    # Normalize file paths: strip the clone_dir prefix so GitHub gets relative paths
    clone_dir_prefix = clone_dir.rstrip("/") + "/"
    for alert in aggregated:
        if alert.get("file", "").startswith(clone_dir_prefix):
            alert["file"] = alert["file"][len(clone_dir_prefix):]

    logger.info(f"SAST aggregation complete: {len(aggregated)} total alerts from {len(scanner_names)} scanners.")
    
    return {
        "alerts": aggregated,
        "languages": detected_languages
    }
