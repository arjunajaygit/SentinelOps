import os
import math
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Heuristic thresholds
ENTROPY_THRESHOLD = 4.5
MIN_STRING_LENGTH = 16

# Dangerous execution sinks
SINKS_REGEX = re.compile(r"(eval|exec|getattr|Buffer\.from|setTimeout|setInterval)\s*\(")
# Basic regex to extract strings (single and double quotes, and backticks)
STRING_REGEX = re.compile(r'(["\'`])((?:(?=(\\?))\3.)*?)\1')

def calculate_shannon_entropy(data: str) -> float:
    """Calculates the Shannon entropy of a string."""
    if not data:
        return 0.0
        
    entropy = 0.0
    length = len(data)
    
    # Calculate character frequencies
    char_counts = {}
    for char in data:
        char_counts[char] = char_counts.get(char, 0) + 1
        
    for count in char_counts.values():
        probability = count / length
        entropy -= probability * math.log2(probability)
        
    return entropy

async def run_entropy_scan(clone_dir: str, diff_files: List[str]) -> List[Dict[str, Any]]:
    """
    Scans for high-entropy strings adjacent to dynamic execution sinks.
    Only scans modified .py, .js, .ts, and .go files.
    """
    alerts = []
    
    target_extensions = {".py", ".js", ".ts", ".go"}
    
    for rel_path in diff_files:
        ext = os.path.splitext(rel_path)[1]
        if ext not in target_extensions:
            continue
            
        full_path = os.path.join(clone_dir, rel_path)
        if not os.path.isfile(full_path):
            continue
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            lines = content.splitlines()
            for line_no, line in enumerate(lines, 1):
                # 1. Check if the line contains a dangerous sink
                if SINKS_REGEX.search(line):
                    # 2. Extract strings from the line
                    strings = STRING_REGEX.findall(line)
                    for match in strings:
                        string_val = match[1]
                        if len(string_val) >= MIN_STRING_LENGTH:
                            entropy = calculate_shannon_entropy(string_val)
                            
                            # 3. Flag if entropy is suspiciously high
                            if entropy > ENTROPY_THRESHOLD:
                                alerts.append({
                                    "scanner": "EntropyGuard",
                                    "severity": "CRITICAL",
                                    "file": rel_path,
                                    "line": line_no,
                                    "description": f"[EntropyGuard] High entropy string ({entropy:.2f}) found near dynamic execution sink. Potential obfuscated payload.",
                                    "confidence": "HIGH"
                                })
        except Exception as e:
            logger.error(f"Error running entropy scan on {rel_path}: {e}")
            
    return alerts
