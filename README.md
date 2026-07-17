# 🛡️ SentinelOps
**Autonomous, Multi-Agent DevSecOps Code Reviewer**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)](#)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker)](#)

*SentinelOps is an event-driven webhook service. It listens to GitHub Pull Requests, indexes the entire repository using localized embeddings (RAG), and uses specialized AI agents to post actionable, inline security and architectural fixes directly to your code.*

---

## 📸 See It In Action
![PR Review Example](assets/pr_review.png)

---

## 🏗️ System Architecture

Unlike standard LLM wrappers, SentinelOps utilizes a stateful, multi-agent LangGraph architecture to prevent hallucination and reduce developer fatigue. It strictly keeps repository context local to ensure data sovereignty.

```mermaid
graph TD
    %% Webhook Entry Point
    PR[GitHub PR Created] -->|Webhook Event| API(FastAPI Orchestrator)
    API -->|1. Dispatch 'Pending' Status| STATUS_PENDING[GitHub Checks API]
    
    %% RAG Pipeline
    subgraph Local Edge Environment
        API -->|2. Clone Repo & Extract Diff| RAG[Codebase Context Agent]
        RAG -->|Chunk & Embed| CHROMA[(ChromaDB Vector Store)]
        HF[Hugging Face all-MiniLM-L6-v2] -.->|Generates Embeddings| CHROMA
    end

    %% SAST Pipeline
    subgraph SAST Orchestrator
        API -->|3. Concurrent Scan| BANDIT[Bandit]
        API -->|3. Concurrent Scan| SEMGREP[Semgrep]
        API -->|3. Concurrent Scan| GITLEAKS[Gitleaks]
        BANDIT --> AGG[Alert Aggregator]
        SEMGREP --> AGG
        GITLEAKS --> AGG
        AGG -->|Raw Alerts| TRIAGE[LLM Triage Analyst]
        TRIAGE -->|Filter False Positives| TRIAGED[Triaged Findings]
    end

    %% Multi-Agent Workflow
    subgraph LangGraph Multi-Agent Workflow
        RAG -->|Diff + Context| SEC[Security Specialist Agent]
        RAG -->|Diff + Context| STY[Code Style Agent]
        
        SEC -->|Vulnerability Findings| SYN[PR Synthesizer Agent]
        STY -->|Maintainability Findings| SYN
        TRIAGED -->|SAST True Positives| SYN
        
        SYN -->|Intelligence Filter| FILTER{Actionable?}
    end

    %% Output
    FILTER -->|Yes| POST[Post Inline GitHub Comment]
    FILTER -->|No| DROP[Silently Drop Noise]
    
    POST -->|4. Dispatch 'Failure' Status| STATUS_FAIL[GitHub Checks API: Block Merge]
    DROP -->|4. Dispatch 'Success' Status| STATUS_PASS[GitHub Checks API: Allow Merge]
```

---

## 🚀 Key Features

- **Multi-Agent Orchestration:** Powered by LangGraph, SentinelOps deploys specialized autonomous agents for analysis:
  - 🔒 **Security Agent:** Hunts for injection flaws, hardcoded secrets, and weak cryptography.
  - 🎨 **Style Agent:** Enforces DRY principles and prevents memory leaks or async blocking.
  - 🛡️ **SAST Orchestrator:** Runs Bandit, Semgrep, and Gitleaks concurrently, then uses an LLM Triage Analyst to filter false positives before merging findings.
  - 🧠 **Synthesizer Agent:** Acts as the Lead Reviewer, deduplicating findings and generating precise Markdown code suggestions that developers can safely copy and paste into their IDE.
- **Defense-in-Depth Security:** Combines deterministic SAST tools (high recall, zero hallucination) with AI agents (contextual understanding) to catch vulnerabilities that neither approach would find alone.
- **RAG Architecture (Retrieval-Augmented Generation):** Unlike standard bots that only read the PR diff, SentinelOps clones the repository and builds a local vector database using **ChromaDB** and **Hugging Face (`all-MiniLM-L6-v2`)**. This gives the AI deep architectural context to prevent hallucinations.
- **Developer Fatigue Prevention:** A dual-layer intelligence filter: the SAST Orchestrator drops tool-level false positives, and the Synthesizer drops pedantic style nits, ensuring developers only see high-value, actionable alerts.
- **Strict CI Gatekeeper:** Integrates directly with the **GitHub Checks API** to dynamically block or allow Pull Request merges based on the severity of the AI's findings.
- **Provider-Agnostic LLM Configuration:** Natively supports any OpenAI-compatible API endpoint (OpenAI, Groq, local Ollama, vLLM) preventing vendor lock-in.
- **Lightning Fast Inference:** Engineered for high-speed analysis using Groq (`llama-3.3-70b-versatile`), providing instant, free inference.
- **Hardened Docker Deployment:** Runs as a non-root user (`sentinel_user`) following the Principle of Least Privilege, with pre-installed SAST toolchain and pre-downloaded ML models for instant cold starts.

---

## ⚡ Core Tech Stack
- **Backend:** FastAPI, Python, Uvicorn
- **AI Orchestration:** LangGraph, LangChain
- **Local RAG Pipeline:** ChromaDB, Hugging Face `sentence-transformers`
- **SAST Toolchain:** Bandit, Semgrep, Gitleaks
- **LLM Inference:** Groq (`llama-3.3-70b-versatile`)
- **Git Operations:** PyGithub, GitPython, GitHub Webhooks
- **Deployment:** Docker

---

## ⚙️ GitHub Configuration Guide

To fully integrate SentinelOps as a strict CI gatekeeper, you must configure your GitHub repository and Personal Access Token properly.

### 1. Personal Access Token Permissions
For Enterprise security, it is highly recommended to use a **Fine-grained Personal Access Token** following the principle of least privilege. 

Grant the following permissions to your token:
- **Administration (Read and write):** Required only if you plan to use `setup_repo.py` to automate branch protection.
- **Commit statuses (Read and write):** Allows SentinelOps to post the yellow/red/green CI gate dots on pull requests.
- **Contents (Read-only):** Allows SentinelOps to securely `git clone` the codebase for RAG context without accidentally modifying your source code.
- **Pull requests (Read and write):** Allows SentinelOps to post the inline code review comments.
- **Metadata (Read-only):** Automatically assigned by GitHub.

*(If you are using a Classic Token, simply check the `repo` scope).*

### 2. Configure Webhooks
1. Go to your Repository Settings > **Webhooks** > **Add webhook**.
2. **Payload URL:** Your server/ngrok URL appended with `/webhook` (e.g., `https://your-ngrok.app/webhook`).
3. **Content type:** `application/json`.
4. **Secret:** Match the `WEBHOOK_SECRET` in your `.env`.
5. **Events:** Select "Let me select individual events", then check **Pull requests**.

### 3. Enforce Strict Branch Protection (Optional)
To physically block the "Merge" button when SentinelOps finds critical security or architectural flaws, you must enforce a Branch Protection rule. We have provided an automated script to configure this for you.

Run the following command in the project root:
```bash
python setup_repo.py --repo your_username/your_repository_name
```
*(This requires your token to have Repository Administration permissions).*

---

## 🚀 Quickstart & Local Testing

### 1. Environment Setup
Create a `.env` file in the root directory. Never commit this file.
```ini
WEBHOOK_SECRET=your_github_webhook_secret
GITHUB_TOKEN=ghp_your_github_pat

# OpenAI-Compatible API Configuration (e.g., Groq, OpenAI, Ollama)
LLM_API_KEY=gsk_your_api_key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

### 2. Run the Development Server Locally
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 🐳 Docker Deployment

SentinelOps is built for easy cloud deployment. The Docker image pre-downloads the Hugging Face models to ensure instant startup and prevents runtime downloads on the server.

**Option 1: Pull from Docker Hub (Fastest)**
```bash
docker pull arjunajaydocker/sentinel-ops
docker run -p 8000:8000 --env-file .env arjunajaydocker/sentinel-ops
```

**Option 2: Build Locally from Source**
```bash
docker build -t sentinel-ops .
docker run -p 8000:8000 --env-file .env sentinel-ops
```

---

## 🔗 Webhook & Cloud Routing

Regardless of how you run it (locally or via Docker), the container exposes a `/webhook` endpoint on port `8000`. 

If you are running this locally on your machine, you must use a tool like **ngrok** to route public GitHub traffic to your local port:
```bash
ngrok http 8000
```
Then, go to your **GitHub Repository -> Settings -> Webhooks**, and add `https://<your-ngrok-url>/webhook` as the Payload URL. 

*(If you deploy this image to a cloud provider like AWS or Render, simply use their provided public URL instead of ngrok!)*
