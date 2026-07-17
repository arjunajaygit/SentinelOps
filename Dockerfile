# Use a slim Python image to keep the container size manageable
FROM python:3.11-slim

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files
# PYTHONUNBUFFERED: Ensures console output is not buffered by Docker
# HF_HOME: Sets a predictable directory for the Hugging Face model cache
# CLONE_DIR: Dedicated directory for cloning PR repositories
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    CLONE_DIR=/app/tmp_repos \
    GITLEAKS_VERSION=8.18.4

# Install system dependencies
# git: Required by GitPython to clone repositories
# build-essential: Required to compile C-extensions for ChromaDB and tokenizers
# wget: Required to download Gitleaks binary
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    wget \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Gitleaks binary (secrets scanner)
RUN wget -qO- "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_arm64.tar.gz" \
    | tar xz -C /usr/local/bin gitleaks \
    && chmod +x /usr/local/bin/gitleaks

# Install Gosec binary
RUN wget -qO- https://raw.githubusercontent.com/securego/gosec/master/install.sh | sh -s -- -b /usr/local/bin v2.20.0

# Set the working directory
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies + SAST tools
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir bandit semgrep njsscan

# OPTIMIZATION: Pre-download the Hugging Face embedding model into the image.
# This prevents the app from downloading it on every server restart/scale-up.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the rest of the application code
COPY . .

# Security: Create a non-root user (Principle of Least Privilege)
RUN useradd --create-home --shell /bin/bash sentinel_user \
    && mkdir -p ${CLONE_DIR} \
    && chown -R sentinel_user:sentinel_user /app

# Demote privileges before running the application
USER sentinel_user

# Expose the FastAPI port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
