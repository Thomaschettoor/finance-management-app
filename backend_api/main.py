"""
Finance Backend API
--------------------
FastAPI application — serves as the bridge between the mobile app
and all backend services.

Base URL:  /api/v1
Docs:      /docs  (Swagger)  |  /redoc  (ReDoc)

Auth:      Supabase JWT   →  Authorization: Bearer <token>

Endpoints:
  Transactions
    GET  /api/v1/transactions                    list (paginated)
    GET  /api/v1/transactions/{id}               single detail
    GET  /api/v1/transactions/{id}/suggestions   behavioral top-3
    POST /api/v1/transactions/{id}/confirm       user confirms category

  Categories
    GET  /api/v1/categories                      list all categories

  Analytics
    GET  /api/v1/analytics/summary               spending by category
    GET  /api/v1/analytics/trends                month-over-month trends

  Health
    GET  /health                                 liveness check
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_api.routes import transactions, categories, analytics

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Finance Management API",
    description="Backend API for the personal finance management app.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Adjust allow_origins in production to your mobile app's domain / scheme.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(transactions.router, prefix=API_PREFIX)
app.include_router(categories.router,   prefix=API_PREFIX)
app.include_router(analytics.router,    prefix=API_PREFIX)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    """Liveness check — returns 200 when the server is running."""
    return {"status": "ok", "version": "1.0.0"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
