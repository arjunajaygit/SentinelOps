import argparse
import sys
import logging
from app.core.github_client import GitHubClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

github_client = GitHubClient()

def main():
    parser = argparse.ArgumentParser(description="Enforce SentinelOps Branch Protection on a GitHub Repository.")
    parser.add_argument("--repo", required=True, help="Full repository name (e.g., username/repo_name)")
    parser.add_argument("--branch", default="main", help="Branch to protect (default: main)")
    
    args = parser.parse_args()
    
    logger.info(f"Setting up SentinelOps branch protection for {args.repo} on branch '{args.branch}'...")
    
    try:
        github_client.enforce_branch_protection(args.repo, args.branch)
        logger.info("✅ Setup complete! SentinelOps is now strictly enforcing CI rules.")
        logger.info("The 'Merge' button will now be blocked if SentinelOps finds critical issues.")
    except Exception as e:
        logger.error(f"❌ Setup failed: {str(e)}")
        logger.error("Ensure your GITHUB_TOKEN has 'Administration' (repo) permissions to change branch protection rules.")
        sys.exit(1)

if __name__ == "__main__":
    main()
