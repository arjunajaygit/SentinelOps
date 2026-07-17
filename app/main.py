import hmac
import hashlib
import logging
import tempfile
import asyncio
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from git import Repo

from app.core.config import settings
from app.core.github_client import GitHubClient
from app.rag.indexer import CodebaseIndexer
from app.agents.graph import build_graph
from app.utils.sast_runner import run_all_sast_scanners

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)
github_client = GitHubClient()
workflow = build_graph()

def verify_signature(payload: bytes, signature: str) -> bool:
    if not settings.WEBHOOK_SECRET:
        return True
    mac = hmac.new(settings.WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

async def process_pull_request(payload: dict):
    action = payload.get("action")
    if action not in ["opened", "synchronize", "reopened"]:
        logger.info(f"Ignoring PR action: {action}")
        return
        
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    
    pr_number = pr_data.get("number")
    repo_full_name = repo_data.get("full_name")
    clone_url = repo_data.get("clone_url")
    
    if settings.GITHUB_TOKEN:
        # Authenticate the clone URL
        clone_url = clone_url.replace("https://", f"https://{settings.GITHUB_TOKEN}@")
        
    head_sha = pr_data.get("head", {}).get("sha")
    
    logger.info(f"Processing PR #{pr_number} for {repo_full_name}")
    
    # 0. Set pending status for CI Gate
    if head_sha:
        await asyncio.to_thread(
            github_client.set_commit_status,
            repo_full_name=repo_full_name,
            commit_id=head_sha,
            state="pending",
            description="SentinelOps is analyzing the code..."
        )
    
    try:
    
        # 1. Clone repository into a temporary directory
        # Using asyncio.to_thread for blocking Git clone and ChromaDB indexing operations
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Cloning {repo_full_name} into {temp_dir}")
            
            def clone_and_index():
                repo = Repo.clone_from(clone_url, temp_dir)
                if head_sha:
                    repo.git.checkout(head_sha)
                    
                # 2. Build RAG Index
                indexer = CodebaseIndexer(repo_path=temp_dir)
                indexer.index_repository()
                return indexer.persist_directory
                
            chroma_persist_dir = await asyncio.to_thread(clone_and_index)
            
            # 2.5. Run SAST scanners concurrently on the cloned repo
            raw_sast_alerts = await run_all_sast_scanners(temp_dir)
        
            # 3. Get diff data
            diff_data = await asyncio.to_thread(github_client.get_pr_files_diff, repo_full_name, pr_number)
            
            if not diff_data:
                logger.info("No modifications found in PR. Skipping analysis.")
                if head_sha:
                    await asyncio.to_thread(
                        github_client.set_commit_status,
                        repo_full_name, head_sha, "success", "No modifications to review."
                    )
                return
                
            # 4. Invoke LangGraph workflow
            initial_state = {
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "commit_id": head_sha,
                "diff_data": diff_data,
                "chroma_persist_dir": chroma_persist_dir,
                "security_findings": [],
                "style_findings": [],
                "raw_sast_alerts": raw_sast_alerts,
                "triaged_sast_findings": [],
                "final_comments": [],
                "critical_issues_found": False
            }
            
            logger.info("Starting Agent Workflow...")
            final_state = await workflow.ainvoke(initial_state)
            
            # 5. Post comments back to GitHub
            comments_to_post = final_state.get("final_comments", [])
            
            valid_comments = []
            for c in comments_to_post:
                if "NO_ACTIONABLE_FINDINGS" not in c['body']:
                    valid_comments.append(c)
                    
            if not valid_comments:
                logger.info("✅ PR is clean (or only had trivial style issues). No comment posted.")
            else:
                logger.info(f"📝 High-value issues found. Posting {len(valid_comments)} comments to GitHub...")
                for comment in valid_comments:
                    await asyncio.to_thread(
                        github_client.post_inline_comment,
                        repo_full_name=repo_full_name,
                        pr_number=pr_number,
                        commit_id=head_sha,
                        path=comment['filename'],
                        line=comment['line'],
                        body=comment['body']
                    )
            
            # 6. Set Final Commit Status (CI Gate)
            if head_sha:
                if valid_comments:
                    await asyncio.to_thread(
                        github_client.set_commit_status,
                        repo_full_name, head_sha, "failure", "Critical issues found. Please fix them."
                    )
                else:
                    await asyncio.to_thread(
                        github_client.set_commit_status,
                        repo_full_name, head_sha, "success", "No critical issues found."
                    )
                
        logger.info(f"Finished processing PR #{pr_number}")

    except Exception as e:
        logger.error(f"Error processing PR #{pr_number}: {e}")
        if head_sha:
            await asyncio.to_thread(
                github_client.set_commit_status,
                repo_full_name, head_sha, "error", f"SentinelOps analysis failed: {str(e)[:40]}"
            )

@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook entrypoint that receives GitHub events.
    """
    signature = request.headers.get("x-hub-signature-256")
    if not signature and settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256 header")
        
    payload = await request.body()
    if signature and not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    event_type = request.headers.get("X-GitHub-Event")
    
    if event_type == "ping":
        return {"msg": "pong"}
    elif event_type == "pull_request":
        try:
            data = await request.json()
            # Queue PR processing in the background to return 202/200 immediately
            background_tasks.add_task(process_pull_request, data)
            return {"msg": "Processing Pull Request in background"}
        except Exception as e:
            logger.error(f"Error parsing webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
            
    return {"msg": f"Event {event_type} ignored"}



