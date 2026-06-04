import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from slate.pipeline.scheduler import start_scheduler
from slate.routers.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(start_scheduler())
    print("scheduler: started", flush=True)
    yield


app = FastAPI(
    title="SLATE",
    description="AI-powered Instagram carousel agent",
    lifespan=lifespan,
)

app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "slate"}
