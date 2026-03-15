FROM python:3.11-slim

# Install git (needed for repo operations)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency spec first for layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/
COPY Replication-Pack/ Replication-Pack/

# Re-install with source
RUN pip install --no-cache-dir -e .

# Default entrypoint: run the ForgeProof pipeline
# GitLab Duo Agent Platform sets env vars:
#   AI_FLOW_CONTEXT, AI_FLOW_INPUT, AI_FLOW_AI_GATEWAY_TOKEN,
#   AI_FLOW_AI_GATEWAY_HEADERS, CI_PROJECT_ID, CI_JOB_TOKEN
ENTRYPOINT ["python", "-m", "forgeproof.main", "run"]
CMD ["--verbose"]
