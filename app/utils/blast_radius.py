import re
import os
import logging
import asyncio
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

# Regex pattern to match function and class definitions across multiple languages
# e.g., def my_func, class MyClass, function my_func, func (r *Receiver) my_func
ENTITY_PATTERN = re.compile(
    r'^\s*(?:def|class|function|func)\s+(?:\([^)]+\)\s+)?([a-zA-Z0-9_]+)\b',
    re.MULTILINE
)

async def _git_grep_entity(clone_dir: str, entity_name: str) -> List[str]:
    """
    Runs git grep to find files that contain the entity_name.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "grep", "-l", entity_name,
            cwd=clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
        
        if process.returncode == 0 and stdout:
            return stdout.decode('utf-8').strip().split('\n')
        return []
    except asyncio.TimeoutError:
        logger.warning(f"git grep for '{entity_name}' timed out.")
        return []
    except Exception as e:
        logger.error(f"Error running git grep for '{entity_name}': {e}")
        return []

async def analyze_blast_radius(clone_dir: str, diff_data: List[Dict[str, Any]]) -> List[str]:
    """
    Extracts modified functions/classes from the PR diff and dynamically identifies files
    in the repository that depend on them.
    
    Args:
        clone_dir (str): The path to the cloned repository.
        diff_data (list): A list of dictionaries representing the PR diffs.
        
    Returns:
        List[str]: A list of relative file paths that depend on the modified entities.
    """
    logger.info("Starting Blast Radius Analysis...")
    diff_files: Set[str] = {f['filename'] for f in diff_data}
    extracted_entities: Set[str] = set()

    # Step 1: Extract modified entities from the diff
    for file_data in diff_data:
        patch = file_data.get('patch', '')
        if not patch:
            continue
        
        # Only look at added/modified lines (starting with +) to find changed definitions
        added_lines = [line[1:] for line in patch.split('\n') if line.startswith('+') and not line.startswith('+++')]
        added_text = '\n'.join(added_lines)
        
        matches = ENTITY_PATTERN.findall(added_text)
        for match in matches:
            extracted_entities.add(match)
            
    if not extracted_entities:
        logger.info("No functions or classes found in diff for blast radius analysis.")
        return []
        
    logger.info(f"Extracted entities for Blast Radius: {extracted_entities}")
    
    dependent_files: Set[str] = set()
    
    # Step 2: Use git grep to find usages of these entities
    tasks = [_git_grep_entity(clone_dir, entity) for entity in extracted_entities]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for grep_result in results:
        if isinstance(grep_result, list):
            for file_path in grep_result:
                file_path = file_path.strip()
                # Step 3: Filter out files that are already part of the diff
                if file_path and file_path not in diff_files:
                    dependent_files.add(file_path)
                    
    logger.info(f"Blast Radius Analysis identified {len(dependent_files)} dependent files.")
    return list(dependent_files)
