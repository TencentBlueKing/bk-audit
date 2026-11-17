FROM python:3.11-bookworm AS builder

ENV PIP_INDEX_URL=https://mirrors.tencent.com/pypi/simple \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN python -m venv /opt/venv
COPY requirements.txt ./

RUN /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install wheel==0.45.1 \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim-bookworm AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
COPY . /app

WORKDIR /app