# Multi-arch (linux/amd64, linux/arm64) — build with:
#   docker buildx build --platform linux/amd64,linux/arm64 -t injection-guard .
#
# Same image serves both deployment targets described in README.md:
# local `docker run` (auth off) and the scaled platform service (auth on,
# via INJECTION_GUARD_AUTH_TOKEN).

FROM python:3.12-slim

# uv per grāmatr's established distribution convention (see README).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system .

# Model weights download on first container start (cached in the image
# layer below is NOT done here deliberately — Meta's license is gated,
# so baking weights into a publicly-pushed image would redistribute
# gated material without each puller having accepted the license
# themselves. Pulling at startup means each deployer authenticates to
# Hugging Face with their own accepted-license token instead.)
ENV HF_HOME=/app/.cache/huggingface

EXPOSE 8730

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8730/health', timeout=3)" || exit 1

CMD ["injection-guard-daemon"]
