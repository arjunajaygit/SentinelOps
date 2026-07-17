import asyncio
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SCANNER_TIMEOUT = 120  # seconds


async def run_bandit(clone_dir: str) -> List[Dict[str, Any]]:
    """
    Runs Bandit (Python SAST) against the cloned repository.
    Bandit exits with code 1 when vulnerabilities are found — this is expected.
    """
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "bandit", "-r", clone_dir, "-f", "json", "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=SCANNER_TIMEOUT
        )

        # Bandit exit codes: 0 = clean, 1 = issues found, other = error
        if process.returncode not in (0, 1):
            logger.warning(f"Bandit exited with unexpected code {process.returncode}: {stderr.decode()[:200]}")
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

        logger.info(f"Bandit scan complete: {len(alerts)} alerts found.")
    except asyncio.TimeoutError:
        logger.error("Bandit scan timed out.")
    except json.JSONDecodeError as e:
        logger.error(f"Bandit produced malformed JSON: {e}")
    except FileNotFoundError:
        logger.warning("Bandit is not installed. Skipping Bandit scan.")
    except Exception as e:
        logger.error(f"Unexpected error running Bandit: {e}")

    return alerts


async def run_semgrep(clone_dir: str) -> List[Dict[str, Any]]:
    """
    Runs Semgrep (multi-language SAST) against the cloned repository.
    Semgrep exits with code 1 when findings are present.
    """
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "semgrep", "scan", "--json", "--quiet", clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=SCANNER_TIMEOUT
        )

        if process.returncode not in (0, 1):
            logger.warning(f"Semgrep exited with unexpected code {process.returncode}: {stderr.decode()[:200]}")
            return []

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

        logger.info(f"Semgrep scan complete: {len(alerts)} alerts found.")
    except asyncio.TimeoutError:
        logger.error("Semgrep scan timed out.")
    except json.JSONDecodeError as e:
        logger.error(f"Semgrep produced malformed JSON: {e}")
    except FileNotFoundError:
        logger.warning("Semgrep is not installed. Skipping Semgrep scan.")
    except Exception as e:
        logger.error(f"Unexpected error running Semgrep: {e}")

    return alerts


async def run_secrets_scan(clone_dir: str) -> List[Dict[str, Any]]:
    """
    Runs Gitleaks (secrets scanner) against the cloned repository.
    Gitleaks exits with code 1 when leaks are found.
    """
    alerts = []
    try:
        process = await asyncio.create_subprocess_exec(
            "gitleaks", "detect", "--source", clone_dir,
            "--report-format", "json", "--report-path", "/dev/stdout",
            "--no-git",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=SCANNER_TIMEOUT
        )

        # Gitleaks exit codes: 0 = clean, 1 = leaks found
        if process.returncode not in (0, 1):
            logger.warning(f"Gitleaks exited with unexpected code {process.returncode}: {stderr.decode()[:200]}")
            return []

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

        logger.info(f"Gitleaks scan complete: {len(alerts)} alerts found.")
    except asyncio.TimeoutError:
        logger.error("Gitleaks scan timed out.")
    except json.JSONDecodeError as e:
        logger.error(f"Gitleaks produced malformed JSON: {e}")
    except FileNotFoundError:
        logger.warning("Gitleaks is not installed. Skipping secrets scan.")
    except Exception as e:
        logger.error(f"Unexpected error running Gitleaks: {e}")

    return alerts


async def run_all_sast_scanners(clone_dir: str) -> List[Dict[str, Any]]:
    """
    Runs all SAST scanners concurrently using asyncio.gather().
    Returns a unified, normalized list of alerts.
    Gracefully degrades: if any scanner fails, returns results from the others.
    """
    logger.info(f"Starting concurrent SAST scans on: {clone_dir}")

    bandit_results, semgrep_results, secrets_results = await asyncio.gather(
        run_bandit(clone_dir),
        run_semgrep(clone_dir),
        run_secrets_scan(clone_dir),
        return_exceptions=True
    )

    aggregated = []
    for scanner_name, result in [
        ("bandit", bandit_results),
        ("semgrep", semgrep_results),
        ("gitleaks", secrets_results)
    ]:
        if isinstance(result, Exception):
            logger.error(f"SAST scanner '{scanner_name}' raised an exception: {result}")
        elif isinstance(result, list):
            aggregated.extend(result)

    # Normalize file paths: strip the clone_dir prefix so GitHub gets relative paths
    clone_dir_prefix = clone_dir.rstrip("/") + "/"
    for alert in aggregated:
        if alert.get("file", "").startswith(clone_dir_prefix):
            alert["file"] = alert["file"][len(clone_dir_prefix):]

    logger.info(f"SAST aggregation complete: {len(aggregated)} total alerts from all scanners.")
    return aggregated
