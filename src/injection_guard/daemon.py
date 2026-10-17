"""
injection-guard-daemon — the only process that loads model weights.
Everything that talks to it (a Claude Code hook, an MCP server, a local
CLI) is a thin HTTP client — see adapters/. Model load happens once at
startup (see model.load_model), not per request.

Same image runs two ways:
  - local `docker run`, loopback-bound, INJECTION_GUARD_AUTH_TOKEN unset
  - the scaled grāmatr platform service, fronted by a load balancer,
    INJECTION_GUARD_AUTH_TOKEN required
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from injection_guard import config, model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("injection_guard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    model.load_model()
    logger.info("injection-guard-daemon ready on %s:%s", config.HOST, config.PORT)
    yield


app = FastAPI(title="injection-guard", lifespan=lifespan)


class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    malicious: bool
    label: str
    score: float
    chunks_scanned: int


def _check_auth(authorization: str | None) -> None:
    if not config.AUTH_TOKEN:
        return  # auth disabled — local trusted deployment
    expected = f"Bearer {config.AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model._model is not None}


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    return model.classify(req.text)


def main() -> None:
    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
