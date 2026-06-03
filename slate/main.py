from fastapi import FastAPI
from slate.routers.webhooks import router as webhooks_router

app = FastAPI(title="SLATE", description="AI-powered Instagram carousel agent")

app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "slate"}
