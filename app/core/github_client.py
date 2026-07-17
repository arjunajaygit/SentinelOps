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

    def set_commit_status(self, repo_full_name: str, commit_id: str, state: str, description: str, context: str = "SentinelOps"):
        """
        Sets the commit status (e.g., pending, success, failure, error) for the Checks API.
        """
        try:
            repo = self.client.get_repo(repo_full_name)
            commit = repo.get_commit(commit_id)
            commit.create_status(
                state=state,
                description=description,
                context=context
            )
            logger.info(f"Successfully set commit status '{state}' for {commit_id[:7]}")
        except Exception as e:
            logger.error(f"Failed to set commit status for {commit_id[:7]}. Error: {str(e)}")

    def enforce_branch_protection(self, repo_full_name: str, branch_name: str = "main"):
        """
        Enforces branch protection on the specified branch, requiring the SentinelOps status check.
        """
        try:
            repo = self.client.get_repo(repo_full_name)
            branch = repo.get_branch(branch_name)
            
            # Require the "SentinelOps" status check to pass before merging
            branch.edit_protection(
                strict=True,
                contexts=["SentinelOps"]
            )
            logger.info(f"Successfully enforced branch protection on {repo_full_name}:{branch_name}")
        except Exception as e:
            logger.error(f"Failed to enforce branch protection on {repo_full_name}:{branch_name}. Error: {str(e)}")
            raise e
