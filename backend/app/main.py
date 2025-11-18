from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import asyncio
import logging
from app.config.database import async_engine, Base, get_async_session
from app.auth import router as auth_router
from app.routers import projects, exports, blob, ratecards, project_prompts, etl
from app.utils import azure_blob
from app.services.etl_pipeline import get_etl_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

# Reduce Azure SDK logging noise
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ---------- App Init ----------
app = FastAPI(
    title="AI-Powered Project Scoping Bot Backend",
    description="AI-Powered Project Scoping Bot Backend",
    version="1.0.0",
)
# ---------- Background ETL Scheduler ----------
_background_task = None

async def periodic_etl_scan():
    """Background task that runs ETL scans every 30 minutes."""
    logger.info("🤖 ETL background scheduler started")

    while True:
        try:
            # Wait 30 minutes between scans
            await asyncio.sleep(30 * 60)

            logger.info("🔄 Running scheduled ETL scan...")
            async for db in get_async_session():
                try:
                    etl = get_etl_pipeline()
                    stats = await etl.scan_and_process_new_documents(db)
                    logger.info(f"✅ Scheduled ETL scan completed: {stats}")
                except Exception as e:
                    logger.error(f"❌ Scheduled ETL scan failed: {e}")
                finally:
                    await db.close()
                break  # Only use first session

        except Exception as e:
            logger.error(f"❌ ETL scheduler error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry

# ---------- Startup ----------
@app.on_event("startup")
async def on_startup():
    global _background_task

    # Create DB tables
    print("Creating database tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")

    # Ensure Blob container exists
    await azure_blob.init_container()
    print("Azure Blob container ready.")

    # Start background ETL scheduler
    _background_task = asyncio.create_task(periodic_etl_scan())
    print("ETL background scheduler started (runs every 30 minutes).")

# ---------- Shutdown ----------
@app.on_event("shutdown")
async def on_shutdown():
    global _background_task
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass
        print("ETL background scheduler stopped.")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Static Files ----------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Routers ----------
app.include_router(auth_router)
app.include_router(projects.router)
app.include_router(exports.router)
app.include_router(blob.router)
app.include_router(ratecards.router)
app.include_router(project_prompts.router)
app.include_router(etl.router)

# ---------- Health Check ----------
@app.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes probes.
    """
    return {"status": "ok"}

