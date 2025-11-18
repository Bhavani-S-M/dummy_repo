"""
ETL Pipeline API Endpoints

Provides admin endpoints for managing the ETL pipeline:
- View pending KB document approvals
- Approve/reject KB updates
- Trigger manual ETL scans
- View processing job status
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
import uuid

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config.database import get_async_session
from app.auth.router import fastapi_users
from app.services.etl_pipeline import get_etl_pipeline
import json

# Only superusers can access ETL endpoints
get_current_superuser = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(prefix="/api/etl", tags=["ETL Pipeline"])


@router.post("/scan")
async def trigger_etl_scan(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Manually trigger an ETL scan of knowledge base documents.

    Only superusers can trigger ETL scans.
    """
    try:
        etl = get_etl_pipeline()
        stats = await etl.scan_and_process_new_documents(db)

        return {
            "status": "success",
            "message": "ETL scan completed",
            "stats": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETL scan failed: {str(e)}")


@router.get("/pending-updates")
async def get_pending_updates(
    status: str = Query("pending", description="Filter by status: pending, approved, rejected"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Get list of pending KB updates requiring admin approval.

    Only superusers can view pending updates.
    """
    try:
        # Query pending updates
        query = (
            select(models.PendingKBUpdate)
            .where(models.PendingKBUpdate.status == status)
            .order_by(desc(models.PendingKBUpdate.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(query)
        pending_updates = result.scalars().all()

        # Enrich with document details
        response_data = []
        for update in pending_updates:
            # Get document info
            doc_result = await db.execute(
                select(models.KnowledgeBaseDocument).where(
                    models.KnowledgeBaseDocument.id == update.new_document_id
                )
            )
            doc = doc_result.scalar_one_or_none()

            if not doc:
                continue

            # Parse related documents
            related_docs = []
            if update.related_documents:
                try:
                    related_docs = json.loads(update.related_documents)
                except:
                    pass

            # Get reviewer info if reviewed
            reviewer_name = None
            if update.reviewed_by:
                user_result = await db.execute(
                    select(models.User).where(models.User.id == update.reviewed_by)
                )
                reviewer = user_result.scalar_one_or_none()
                if reviewer:
                    reviewer_name = reviewer.username

            response_data.append({
                "id": str(update.id),
                "document": {
                    "id": str(doc.id),
                    "file_name": doc.file_name,
                    "blob_path": doc.blob_path,
                    "file_size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                },
                "update_type": update.update_type,
                "similarity_score": update.similarity_score,
                "reason": update.reason,
                "related_documents": related_docs,
                "status": update.status,
                "reviewed_by": reviewer_name,
                "reviewed_at": update.reviewed_at.isoformat() if update.reviewed_at else None,
                "admin_comment": update.admin_comment,
                "created_at": update.created_at.isoformat()
            })

        return {
            "status": "success",
            "count": len(response_data),
            "pending_updates": response_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending updates: {str(e)}")


@router.post("/approve/{pending_update_id}")
async def approve_kb_update(
    pending_update_id: uuid.UUID,
    admin_comment: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Approve a pending KB update and process the document.

    Only superusers can approve updates.
    """
    try:
        etl = get_etl_pipeline()
        result = await etl.approve_and_process(
            db=db,
            pending_update_id=str(pending_update_id),
            admin_user_id=str(current_user.id),
            admin_comment=admin_comment
        )

        return {
            "status": "success",
            "message": "KB update approved and processed",
            **result
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.post("/reject/{pending_update_id}")
async def reject_kb_update(
    pending_update_id: uuid.UUID,
    admin_comment: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Reject a pending KB update.

    Only superusers can reject updates.
    """
    try:
        etl = get_etl_pipeline()
        result = await etl.reject_update(
            db=db,
            pending_update_id=str(pending_update_id),
            admin_user_id=str(current_user.id),
            admin_comment=admin_comment
        )

        return {
            "status": "success",
            "message": "KB update rejected",
            **result
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")


@router.get("/processing-jobs")
async def get_processing_jobs(
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, completed, failed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Get list of document processing jobs.

    Only superusers can view processing jobs.
    """
    try:
        query = select(models.DocumentProcessingJob).order_by(
            desc(models.DocumentProcessingJob.created_at)
        ).limit(limit).offset(offset)

        if status:
            query = query.where(models.DocumentProcessingJob.status == status)

        result = await db.execute(query)
        jobs = result.scalars().all()

        # Enrich with document details
        response_data = []
        for job in jobs:
            doc_result = await db.execute(
                select(models.KnowledgeBaseDocument).where(
                    models.KnowledgeBaseDocument.id == job.document_id
                )
            )
            doc = doc_result.scalar_one_or_none()

            response_data.append({
                "id": str(job.id),
                "document": {
                    "id": str(doc.id) if doc else None,
                    "file_name": doc.file_name if doc else "Unknown"
                },
                "status": job.status,
                "chunks_processed": job.chunks_processed,
                "vectors_created": job.vectors_created,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            })

        return {
            "status": "success",
            "count": len(response_data),
            "jobs": response_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch processing jobs: {str(e)}")


@router.get("/kb-documents")
async def get_kb_documents(
    is_vectorized: Optional[bool] = Query(None, description="Filter by vectorization status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Get list of knowledge base documents.

    Only superusers can view KB documents.
    """
    try:
        query = select(models.KnowledgeBaseDocument).order_by(
            desc(models.KnowledgeBaseDocument.uploaded_at)
        ).limit(limit).offset(offset)

        if is_vectorized is not None:
            query = query.where(models.KnowledgeBaseDocument.is_vectorized == is_vectorized)

        result = await db.execute(query)
        documents = result.scalars().all()

        response_data = [{
            "id": str(doc.id),
            "file_name": doc.file_name,
            "blob_path": doc.blob_path,
            "file_size": doc.file_size,
            "file_hash": doc.file_hash,
            "is_vectorized": doc.is_vectorized,
            "vector_count": doc.vector_count,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "vectorized_at": doc.vectorized_at.isoformat() if doc.vectorized_at else None,
            "last_checked": doc.last_checked.isoformat() if doc.last_checked else None
        } for doc in documents]

        return {
            "status": "success",
            "count": len(response_data),
            "documents": response_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch KB documents: {str(e)}")


@router.get("/stats")
async def get_etl_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Get ETL pipeline statistics.

    Only superusers can view ETL stats.
    """
    try:
        # Count documents
        total_docs_result = await db.execute(select(models.KnowledgeBaseDocument))
        total_docs = len(total_docs_result.scalars().all())

        vectorized_docs_result = await db.execute(
            select(models.KnowledgeBaseDocument).where(
                models.KnowledgeBaseDocument.is_vectorized == True
            )
        )
        vectorized_docs = len(vectorized_docs_result.scalars().all())

        # Count pending approvals
        pending_approvals_result = await db.execute(
            select(models.PendingKBUpdate).where(
                models.PendingKBUpdate.status == "pending"
            )
        )
        pending_approvals = len(pending_approvals_result.scalars().all())

        # Count processing jobs by status
        jobs_result = await db.execute(select(models.DocumentProcessingJob))
        all_jobs = jobs_result.scalars().all()

        jobs_by_status = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        for job in all_jobs:
            jobs_by_status[job.status] = jobs_by_status.get(job.status, 0) + 1

        return {
            "status": "success",
            "stats": {
                "total_documents": total_docs,
                "vectorized_documents": vectorized_docs,
                "unvectorized_documents": total_docs - vectorized_docs,
                "pending_approvals": pending_approvals,
                "processing_jobs": jobs_by_status
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.post("/reset-failed-documents")
async def reset_failed_documents(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_superuser)
):
    """
    Reset failed documents to allow reprocessing.

    This marks all documents with failed processing jobs as not vectorized,
    so they will be reprocessed on the next ETL scan.

    Only superusers can reset failed documents.
    """
    try:
        # Find all failed processing jobs
        failed_jobs_result = await db.execute(
            select(models.DocumentProcessingJob).where(
                models.DocumentProcessingJob.status == "failed"
            )
        )
        failed_jobs = failed_jobs_result.scalars().all()

        reset_count = 0
        for job in failed_jobs:
            # Get the document
            doc_result = await db.execute(
                select(models.KnowledgeBaseDocument).where(
                    models.KnowledgeBaseDocument.id == job.document_id
                )
            )
            doc = doc_result.scalar_one_or_none()

            if doc:
                # Mark as not vectorized so it will be reprocessed
                doc.is_vectorized = False
                doc.vectorized_at = None
                doc.vector_count = 0
                doc.qdrant_point_ids = None
                reset_count += 1

        await db.commit()

        return {
            "status": "success",
            "message": f"Reset {reset_count} failed documents for reprocessing",
            "reset_count": reset_count
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset documents: {str(e)}")

