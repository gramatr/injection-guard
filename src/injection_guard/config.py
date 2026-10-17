import os

# Env-driven config so the SAME container image serves both deployment
# targets: local `docker run` (auth off, loopback-bound) and the scaled
# grāmatr platform service (auth required, fronted by a load balancer).

HOST = os.environ.get("INJECTION_GUARD_HOST", "127.0.0.1")
PORT = int(os.environ.get("INJECTION_GUARD_PORT", "8730"))
MODEL_ID = os.environ.get("INJECTION_GUARD_MODEL_ID", "meta-llama/Llama-Prompt-Guard-2-86M")

# When set, every request must carry `Authorization: Bearer <token>`.
# Leave unset for local trusted use (advanced Docker tier).
AUTH_TOKEN = os.environ.get("INJECTION_GUARD_AUTH_TOKEN")
