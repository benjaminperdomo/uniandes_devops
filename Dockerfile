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

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "application:application"]
