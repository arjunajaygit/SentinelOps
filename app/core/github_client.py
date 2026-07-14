import logging
from typing import List, Dict, Any, Optional
from github import Github, Auth
from github.PullRequest import PullRequest
from app.core.config import settings

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self):
        auth = Auth.Token(settings.GITHUB_TOKEN)
        self.client = Github(auth=auth)

    def get_pull_request(self, repo_full_name: str, pr_number: int) -> PullRequest:
        """Fetch a Pull Request object."""
        repo = self.client.get_repo(repo_full_name)
        return repo.get_pull(pr_number)

    def get_pr_files_diff(self, repo_full_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetches the modified files and their patches for a PR.
        """
        pr = self.get_pull_request(repo_full_name, pr_number)
        files = pr.get_files()
        
        diff_data = []
        for file in files:
            # We only care about added/modified files and files with patches
            if file.status in ['added', 'modified'] and file.patch:
                diff_data.append({
                    'filename': file.filename,
                    'status': file.status,
                    'additions': file.additions,
                    'deletions': file.deletions,
                    'patch': file.patch,
                    'raw_url': file.raw_url
                })
                
        return diff_data

    def post_inline_comment(
        self, 
        repo_full_name: str, 
        pr_number: int, 
        commit_id: str, 
        path: str, 
        line: int, 
        body: str
    ):
        """
        Posts an inline comment on a specific line of a file in a Pull Request.
        """
        pr = self.get_pull_request(repo_full_name, pr_number)
        repo = self.client.get_repo(repo_full_name)
        commit = repo.get_commit(commit_id)
        
        try:
            # Note: The side is typically 'RIGHT' for additions/modifications in the PR
            pr.create_review_comment(
                body=body,
                commit=commit,
                path=path,
                line=line,
                side="RIGHT"
            )
            logger.info(f"Successfully posted inline comment to {path}:{line}")
        except Exception as e:
            logger.error(f"Failed to post inline comment to {path}:{line}. Error: {str(e)}")
            
    def get_latest_commit_sha(self, repo_full_name: str, pr_number: int) -> str:
        """
        Gets the HEAD commit SHA for the PR to associate comments with the latest changes.
        """
        pr = self.get_pull_request(repo_full_name, pr_number)
        # Get the last commit in the PR
        commits = list(pr.get_commits())
        if not commits:
            raise ValueError(f"No commits found in PR #{pr_number}")
        return commits[-1].sha
