import os
import re
import json
import logging
import aiohttp
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def run_osv_scan(clone_dir: str, diff_files: List[str]) -> List[Dict[str, Any]]:
    """
    Scans dependencies modified in the PR against the OSV API.
    Extracts dependencies from requirements.txt and package.json.
    """
    alerts = []
    
    # 1. Collect dependencies
    packages_to_check = []
    
    for rel_path in diff_files:
        if not (rel_path.endswith("requirements.txt") or rel_path.endswith("package.json")):
            continue
            
        full_path = os.path.join(clone_dir, rel_path)
        if not os.path.isfile(full_path):
            continue
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            if rel_path.endswith("requirements.txt"):
                # Basic parsing for package==version
                for line in content.splitlines():
                    line = line.strip()
                    if "==" in line and not line.startswith("#"):
                        parts = line.split("==")
                        if len(parts) == 2:
                            pkg_name, pkg_version = parts[0].strip(), parts[1].strip()
                            # Strip environment markers if any
                            pkg_version = pkg_version.split(";")[0].strip()
                            packages_to_check.append({
                                "version": pkg_version,
                                "package": {"name": pkg_name, "ecosystem": "PyPI"},
                                "file": rel_path
                            })
                            
            elif rel_path.endswith("package.json"):
                data = json.loads(content)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for pkg_name, pkg_version in deps.items():
                    # Strip ^ or ~ from version
                    clean_version = re.sub(r'^[~^]', '', pkg_version)
                    packages_to_check.append({
                        "version": clean_version,
                        "package": {"name": pkg_name, "ecosystem": "npm"},
                        "file": rel_path
                    })
        except Exception as e:
            logger.error(f"Error parsing {rel_path} for OSV scan: {e}")

    if not packages_to_check:
        return alerts

    # 2. Query OSV API
    # https://api.osv.dev/v1/query supports single package queries. We'll do batch queries using /querybatch
    try:
        queries = [{"version": pkg["version"], "package": pkg["package"]} for pkg in packages_to_check]
        payload = {"queries": queries}
        
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.osv.dev/v1/querybatch", json=payload, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"OSV API returned status {response.status}")
                    return alerts
                
                result = await response.json()
                results = result.get("results", [])
                
                # Match results back to packages
                for idx, res in enumerate(results):
                    vulns = res.get("vulns", [])
                    if vulns:
                        pkg_info = packages_to_check[idx]
                        for vuln in vulns:
                            cve_id = vuln.get("id", "UNKNOWN_VULN")
                            summary = vuln.get("summary", "Vulnerable dependency detected.")
                            
                            alerts.append({
                                "scanner": "osv",
                                "severity": "CRITICAL",  # Threat hunting usually surfaces high/critical
                                "file": pkg_info["file"],
                                "line": 0,
                                "description": f"[{cve_id}] {pkg_info['package']['name']}@{pkg_info['version']} - {summary}",
                                "confidence": "HIGH"
                            })
                            
    except Exception as e:
        logger.error(f"Failed to query OSV API: {e}")
        
    return alerts
