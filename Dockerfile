# Inspired by https://testdriven.io/blog/docker-best-practices/#using-python-virtual-environments

ARG python_tag=3.12-alpine3.19

# =================================================
# Base stage - dependencies and application install
# =================================================
FROM python:$python_tag as builder

COPY ./app/pgtester /app/pgtester
COPY ./app/pyproject.toml /app/
COPY ./app/requirements.txt /app/
WORKDIR /app

RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
RUN pip install .

RUN pip uninstall -y setuptools

# ==================================
# Final stage - the production image
# ==================================
FROM python:$python_tag

# Non-root user
RUN addgroup --gid 2000 pgtester && adduser -H -D -G pgtester --uid 2000 pgtester

# App-wrapper (HTTP server) to installed environment from base
COPY app/gunicorn_config.py /app/
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Configure application execution
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
USER 2000
ENTRYPOINT [ "gunicorn", "--config", "gunicorn_config.py" ]

# Not really needed when running in K8S but provided according to Docker best-practices
HEALTHCHECK CMD netstat -tplen | grep "0.0.0.0:8080 .*python" > /dev/null || exit 1
