# Base images come from the Amazon ECR Public mirror of Docker Hub's official images:
# CodeBuild shares IP addresses, so anonymous pulls from Docker Hub hit its rate limit.
ARG BASE_REGISTRY=public.ecr.aws/docker/library/

# ---------- base: application and runtime dependencies ----------
FROM ${BASE_REGISTRY}python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY application.py VERSION ./
COPY app ./app

# ---------- test: runs the unit tests inside the same image ----------
FROM base AS test

COPY requirements-dev.txt pytest.ini ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests

CMD ["pytest", "--junitxml=reports/junit.xml"]

# ---------- runtime: image that gets published to Amazon ECR ----------
FROM base AS runtime

RUN useradd --create-home --uid 10001 appuser
USER appuser

# New Relic APM agent, configured only through environment variables (no newrelic.ini).
# NEW_RELIC_LICENSE_KEY and NEW_RELIC_APP_NAME come from the environment where the container runs:
# docker-compose.yml (.env file) locally and taskdef.json (Parameter Store) in AWS Fargate.
# Without a license key the agent stays inactive and the application runs normally.
ENV NEW_RELIC_LOG=stdout \
    NEW_RELIC_LOG_LEVEL=info \
    NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true

EXPOSE 8000
ENTRYPOINT ["newrelic-admin", "run-program"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "application:application"]
