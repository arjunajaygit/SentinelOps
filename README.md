# SentinelOps 🛡️

SentinelOps is a containerized, AI-powered DevSecOps code reviewer that automatically analyzes GitHub Pull Requests. It acts as an autonomous intelligence filter, enforcing security best practices and architectural standards while aggressively filtering out trivial developer noise.

## 🚀 Features

- **Multi-Agent Orchestration:** Powered by LangGraph, SentinelOps deploys specialized autonomous agents for parallel analysis:
  - 🔒 **Security Agent:** Hunts for injection flaws, hardcoded secrets, and weak cryptography.
  - 🎨 **Style Agent:** Enforces DRY principles and prevents memory leaks or async blocking.
  - 🧠 **Synthesizer Agent:** Acts as the Lead Reviewer, deduplicating findings and generating precise Markdown code suggestions.
- **RAG Architecture (Retrieval-Augmented Generation):** Unlike standard bots that only read the PR diff, SentinelOps clones the repository and builds a local vector database using **ChromaDB** and **Hugging Face (`all-MiniLM-L6-v2`)**. This gives the AI deep architectural context to prevent hallucinations.
- **Developer Fatigue Prevention:** A strict intelligence filter explicitly drops pedantic noise like formatting nits and missing docstrings, ensuring developers only see high-value, actionable alerts.
- **Lightning Fast Inference:** Powered by **Groq** (`llama-3.3-70b-versatile`), providing instant, free inference.
- **Cloud-Ready Containerization:** Fully containerized via Docker with DevSecOps footprint optimizations (CPU-only PyTorch) for fast, lightweight deployment.

---

## 🛠️ Local Setup

1. **Clone the repository and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the root directory (do not use quotes around values):
   ```ini
   GITHUB_TOKEN=github_pat_...
   GROQ_API_KEY=gsk_...
   WEBHOOK_SECRET=your_secret_string
   ```

3. **Run the Development Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Expose to GitHub:**
   Run an ngrok tunnel to expose your local port:
   ```bash
   ngrok http 8000
   ```
   Add `https://<your-ngrok-url>/webhook` as the Payload URL in your GitHub Repository Webhooks settings.

---

## 🐳 Docker Deployment

SentinelOps is built for easy cloud deployment. The Dockerfile is highly optimized to run locally or on AWS/Render.

**Build the Image:**
```bash
docker build -t sentinel-ops .
```

**Run the Container:**
```bash
docker run -p 8000:8000 --env-file .env sentinel-ops
```

*(Note: The container exposes port 8000. Ensure your webhook routes to this port).*
