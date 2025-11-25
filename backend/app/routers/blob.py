from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Literal
from app.utils import azure_blob
from app.auth.router import fastapi_users
from app.config.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
import io, mimetypes, logging

logger = logging.getLogger(__name__)

get_current_superuser = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(prefix="/api/blobs", tags=["Azure Blobs"])

VALID_BASES = ("projects", "knowledge_base")


def _validate_base(base: str) -> str:
    if base not in VALID_BASES:
        raise HTTPException(400, f"Invalid base '{base}'. Must be one of {VALID_BASES}")
    return base


async def _trigger_etl_scan():
    """Background task to trigger ETL scan after KB document upload."""
    try:
        from app.services.etl_pipeline import get_etl_pipeline
        from app.config.database import AsyncSessionLocal

        # Create a new database session for the background task
        async with AsyncSessionLocal() as db:
            etl = get_etl_pipeline()
            stats = await etl.scan_and_process_new_documents(db)
            logger.info(f"✅ Post-upload ETL scan completed: {stats}")
    except Exception as e:
        logger.error(f"❌ Post-upload ETL scan failed: {e}")


# Uploads
@router.post("/upload/file")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    folder: str = Form(""),
    base: Literal["projects", "knowledge_base"] = Form("knowledge_base"),
    db: AsyncSession = Depends(get_async_session)
):
    try:
        base = _validate_base(base)
        folder = folder.strip().rstrip("/")
        safe_name = file.filename.replace(" ", "_")
        blob_name = f"{folder}/{safe_name}" if folder else safe_name
        blob_name = blob_name.strip("/")

        data = await file.read()
        path = await azure_blob.upload_bytes(data, blob_name, base)

        # If uploading to knowledge_base, trigger ETL scan in background
        if base == "knowledge_base":
            logger.info(f"📤 KB document uploaded: {path}, triggering ETL scan...")
            background_tasks.add_task(_trigger_etl_scan)

        return {"status": "success", "blob": path}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {e}")


@router.post("/upload/folder")
async def upload_folder(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    folder: str = Form(""),
    base: Literal["projects", "knowledge_base"] = Form("knowledge_base"),
    db: AsyncSession = Depends(get_async_session)
):
    try:
        base = _validate_base(base)
        folder = folder.strip().rstrip("/")
        uploaded = []

        for file in files:
            relative_path = file.filename.replace(" ", "_")
            blob_name = f"{folder}/{relative_path}" if folder else relative_path
            blob_name = blob_name.strip("/")

            data = await file.read()
            path = await azure_blob.upload_bytes(data, blob_name, base)
            uploaded.append(path)

        # If uploading to knowledge_base, trigger ETL scan in background
        if base == "knowledge_base":
            logger.info(f"📤 {len(uploaded)} KB documents uploaded, triggering ETL scan...")
            background_tasks.add_task(_trigger_etl_scan)

        return {"status": "success", "files": uploaded}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {e}")

# Explorer-Style Listing
@router.get("/explorer/{base}")
async def explorer_tree(base: Literal["projects", "knowledge_base"]):
    try:
        base = _validate_base(base)
        tree = await azure_blob.explorer(base)
        return {
            "status": "success",
            "base": base,
            "children": tree["children"],
        }
    except Exception as e:
        raise HTTPException(500, f"Explorer listing failed: {e}")


# Download
@router.get("/download/{blob_name:path}")
async def download_blob(blob_name: str, base: Literal["projects", "knowledge_base"] = Query(...)):
    try:
        base = _validate_base(base)
        blob_bytes = await azure_blob.download_bytes(blob_name, base)
        file_like = io.BytesIO(blob_bytes)
        filename = blob_name.split("/")[-1]
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        return StreamingResponse(
            file_like,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(404, f"Blob not found: {e}")

# Preview
@router.get("/preview/{blob_name:path}")
async def preview_blob(blob_name: str, base: Literal["projects", "knowledge_base"] = Query(...)):
    try:
        base = _validate_base(base)
        blob_bytes = await azure_blob.download_bytes(blob_name, base)
        file_like = io.BytesIO(blob_bytes)
        filename = blob_name.split("/")[-1]
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        return StreamingResponse(
            file_like,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(404, f"Blob not found: {e}")


# Delete
@router.delete("/delete/file/{blob_name:path}")
async def delete_file(blob_name: str, base: Literal["projects", "knowledge_base"] = Query(...)):
    try:
        base = _validate_base(base)
        await azure_blob.delete_blob(blob_name, base)
        return {"status": "success", "deleted": f"{base}/{blob_name}"}
    except Exception as e:
        raise HTTPException(404, f"File not found: {e}")


@router.delete("/delete/folder/{folder_name:path}")
async def delete_folder(
    folder_name: str,
    base: Literal["projects", "knowledge_base"] = Query(...),
    db: AsyncSession = Depends(get_async_session)
):
    try:
        base = _validate_base(base)

        # If deleting from knowledge_base, also clean up database and Qdrant
        if base == "knowledge_base":
            from sqlalchemy import select, delete
            from app.models import KnowledgeBaseDocument
            from app.config.config import QDRANT_COLLECTION, CASE_STUDY_COLLECTION
            from app.utils.ai_clients import get_qdrant_client
            from qdrant_client import models as models_qdrant

            # Construct blob path prefix
            blob_prefix = f"{base}/{folder_name}/"
            logger.info(f"🗑️ Cleaning up KB documents with prefix: {blob_prefix}")

            # Find all documents under this folder
            result = await db.execute(
                select(KnowledgeBaseDocument).where(
                    KnowledgeBaseDocument.blob_path.like(f"{blob_prefix}%")
                )
            )
            documents = result.scalars().all()

            if documents:
                logger.info(f"🗑️ Found {len(documents)} KB documents to delete")
                qdrant_client = get_qdrant_client()

                # Delete vectors from Qdrant for each document
                for doc in documents:
                    try:
                        # Determine which collection based on document_type
                        collection = CASE_STUDY_COLLECTION if doc.document_type == "case_study" else QDRANT_COLLECTION

                        qdrant_client.delete(
                            collection_name=collection,
                            points_selector=models_qdrant.FilterSelector(
                                filter=models_qdrant.Filter(
                                    must=[
                                        models_qdrant.FieldCondition(
                                            key="document_id",
                                            match=models_qdrant.MatchValue(value=str(doc.id))
                                        )
                                    ]
                                )
                            )
                        )
                        logger.info(f"✅ Deleted vectors for: {doc.file_name} from {collection}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to delete vectors for {doc.file_name}: {e}")

                # Delete database records
                await db.execute(
                    delete(KnowledgeBaseDocument).where(
                        KnowledgeBaseDocument.blob_path.like(f"{blob_prefix}%")
                    )
                )
                await db.commit()
                logger.info(f"✅ Deleted {len(documents)} KB document records from database")

        # Delete blob files
        deleted = await azure_blob.delete_folder(folder_name, base)
        if not deleted:
            raise HTTPException(404, "Folder is empty or not found")
        return {"status": "success", "deleted": deleted}
    except Exception as e:
        raise HTTPException(404, f"Folder not found: {e}")


# SAS Token
@router.get("/sas-token")
async def get_sas_token(hours: int = 1):
    try:
        url = azure_blob.generate_sas_url(hours)
        return {"status": "success", "sas_url": url}
    except Exception as e:
        raise HTTPException(500, f"SAS generation failed: {e}")
