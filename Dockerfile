FROM python:3.11-slim

# Install git (needed for repo clone in Duo Agent Platform)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy everything needed for install + runtime
COPY pyproject.toml .
COPY src/ src/
COPY Replication-Pack/ Replication-Pack/
COPY demo/ demo/
COPY tests/ tests/

# Install with dev deps (pytest needed by eval phase, ruff already in main deps)
RUN pip install --no-cache-dir -e ".[dev]"

# Default entrypoint: run the ForgeProof pipeline
# GitLab Duo Agent Platform sets env vars:
#   AI_FLOW_CONTEXT, AI_FLOW_INPUT, AI_FLOW_AI_GATEWAY_TOKEN,
#   AI_FLOW_AI_GATEWAY_HEADERS, CI_PROJECT_ID, CI_JOB_TOKEN
ENTRYPOINT ["python", "-m", "forgeproof.main", "run"]
CMD ["--verbose"]
