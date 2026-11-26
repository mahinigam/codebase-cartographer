# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

COPY rust-toolchain.toml /build/rust-toolchain.toml
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.94.0 --profile minimal \
    && pip install --no-cache-dir "maturin>=1.7,<2.0"

COPY pyproject.toml /build/pyproject.toml
COPY rust /build/rust
COPY app /build/app

RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/rust/target \
    maturin build --release --out /wheels

FROM python:3.11-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels/*.whl /tmp/wheels/

RUN pip install --no-cache-dir /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
