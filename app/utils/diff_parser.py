from typing import List, Dict, Any
import re

def parse_file_patch(patch_text: str) -> List[Dict[str, Any]]:
    """
    Parses a unified diff patch for a single file (like what GitHub API returns in file.patch).
    Returns a list of parsed hunks with their respective added/removed lines and line numbers.
    """
    if not patch_text:
        return []

    hunks = []
    current_hunk = None
    lines = patch_text.splitlines()
    
    # We maintain the actual line numbers in the new file (right side)
    current_new_line = 0
    current_old_line = 0
    
    for line in lines:
        if line.startswith('@@'):
            # Parse @@ -old_line,old_count +new_line,new_count @@
            match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                old_start = int(match.group(1))
                new_start = int(match.group(3))
                
                current_hunk = {
                    'header': line,
                    'old_start': old_start,
                    'new_start': new_start,
                    'lines': []
                }
                hunks.append(current_hunk)
                current_old_line = old_start
                current_new_line = new_start
        elif current_hunk is not None:
            if line.startswith('+'):
                current_hunk['lines'].append({
                    'type': 'add',
                    'content': line[1:],
                    'line_number': current_new_line
                })
                current_new_line += 1
            elif line.startswith('-'):
                current_hunk['lines'].append({
                    'type': 'delete',
                    'content': line[1:],
                    'line_number': current_old_line
                })
                current_old_line += 1
            elif not line.startswith('\\ No newline'):
                # Context line (starts with space or is empty)
                content = line[1:] if line.startswith(' ') else line
                current_hunk['lines'].append({
                    'type': 'context',
                    'content': content,
                    'old_line_number': current_old_line,
                    'new_line_number': current_new_line
                })
                current_old_line += 1
                current_new_line += 1

    return hunks

def extract_added_lines(hunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts only the added lines from parsed hunks, as these are typically 
    what we want to comment on for new security/style issues.
    """
    added_lines = []
    for hunk in hunks:
        for line in hunk['lines']:
            if line['type'] == 'add':
                added_lines.append(line)
    return added_lines
