from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import close_connection, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    close_connection()


app = FastAPI(
    title="Verdant Goods Chargeback Prevention API",
    description="Real-time fraud risk scoring and chargeback pattern analysis",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


from app.routers import chargebacks, rules, transactions  # noqa: E402

app.include_router(transactions.router, prefix="/api/v1")
app.include_router(chargebacks.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
