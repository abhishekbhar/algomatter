from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init DB pool, Redis
    yield
    # shutdown: close pools


app = FastAPI(title="GainGuard", version="0.1.0", lifespan=lifespan)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
