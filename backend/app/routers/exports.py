import uuid, json, re, logging
from typing import Any, Dict, Optional
from app.utils import azure_blob

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app import crud as projects
from app.config.database import get_async_session
from app.auth.router import fastapi_users
from app.utils import export, scope_engine

logger = logging.getLogger(__name__)
current_active_user = fastapi_users.current_user(active=True)

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["Export"])


# Helpers
async def _get_project(project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> models.Project:
    project = await projects.get_project(db, project_id=project_id, owner_id=user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")
    await db.refresh(project, attribute_names=["files"])
    return project


async def _load_finalized_scope(project: models.Project) -> Optional[Dict[str, Any]]:
    for f in project.files:
        if f.file_name == "finalized_scope.json":
            try:
                blob_bytes = await azure_blob.download_bytes(f.file_path)
                return json.loads(blob_bytes.decode("utf-8"))
            except Exception as e:
                logging.warning(f"Failed to load finalized scope from blob {f.file_path}: {e}")
                return None
    return None


def _safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", (name or "").strip().lower())


async def _fetch_related_case_study(project_id: uuid.UUID, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Fetch the related case study for a project.

    Returns case study data or None if no match found.
    """
    try:
        from app.utils.ai_clients import embed_text_ollama, get_qdrant_client
        from app.config.config import CASE_STUDY_COLLECTION
        from app import crud as projects

        # Fetch project
        db_project = await projects.get_project_by_id(db, project_id=project_id)
        if not db_project:
            return None

        # Load finalized_scope.json to get executive summary
        blob_name = f"projects/{project_id}/finalized_scope.json"
        try:
            scope_bytes = await azure_blob.download_bytes(blob_name)
            scope_data = json.loads(scope_bytes.decode("utf-8"))
        except:
            return None

        # Get executive summary
        executive_summary = scope_data.get("project_summary", {}).get("executive_summary", "")
        if not executive_summary or len(executive_summary.strip()) < 20:
            return None

        # Generate embedding
        embeddings = embed_text_ollama([executive_summary])
        if not embeddings or not embeddings[0]:
            return None

        query_vector = embeddings[0]

        # Search Qdrant
        qdrant_client = get_qdrant_client()

        # First search without threshold to see what we have
        all_results = qdrant_client.search(
            collection_name=CASE_STUDY_COLLECTION,
            query_vector=query_vector,
            limit=1
        )

        if not all_results or len(all_results) == 0:
            return None

        best_score = float(all_results[0].score)

        # Apply threshold
        SIMILARITY_THRESHOLD = 0.70
        if best_score < SIMILARITY_THRESHOLD:
            return None

        # Get the best match
        best_match = all_results[0]
        payload = best_match.payload or {}

        # Parse case study metadata
        case_study_json = payload.get("case_study_metadata")
        if case_study_json:
            case_study_data = json.loads(case_study_json) if isinstance(case_study_json, str) else case_study_json
        else:
            case_study_data = {}

        return {
            "matched": True,
            "client_name": case_study_data.get("client_name", "Unknown Client"),
            "overview": case_study_data.get("overview", ""),
            "solution": case_study_data.get("solution", ""),
            "impact": case_study_data.get("impact", ""),
            "similarity_score": best_score,
            "source": f"{payload.get('file_name', '')} (Slides {case_study_data.get('slide_range', '')})"
        }
    except Exception as e:
        logger.warning(f"Failed to fetch case study for project {project_id}: {e}")
        return None


async def _ensure_scope(project: models.Project, db: AsyncSession) -> Dict[str, Any]:
    scope = await _load_finalized_scope(project)
    if not scope:
        raw_scope = await scope_engine.generate_project_scope(db, project)
        scope = export.generate_json_data(raw_scope or {})

    # Add related case study to scope
    case_study = await _fetch_related_case_study(project.id, db)
    if case_study:
        scope["related_case_study"] = case_study

    return scope


# PREVIEW EXPORTS

@router.post("/preview/json")
async def preview_json_from_scope(
    project_id: uuid.UUID,
    scope: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(current_active_user),
):
    project = await _get_project(project_id, current_user.id, db)
    finalized = await _load_finalized_scope(project)
    if (not scope or len(scope) == 0) and finalized:
        # Add case study to finalized scope
        case_study = await _fetch_related_case_study(project_id, db)
        if case_study:
            finalized["related_case_study"] = case_study
        return finalized

    # For preview scope, also try to add case study
    preview_scope = export.generate_json_data(scope or {})
    case_study = await _fetch_related_case_study(project_id, db)
    if case_study:
        preview_scope["related_case_study"] = case_study
    return preview_scope


@router.post("/preview/excel")
async def preview_excel_from_scope(
    project_id: uuid.UUID,
    scope: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(current_active_user),
):
    project = await _get_project(project_id, current_user.id, db)
    finalized = await _load_finalized_scope(project)
    normalized = export.generate_json_data(scope or {}) if not finalized else finalized

    # Add case study to preview
    case_study = await _fetch_related_case_study(project_id, db)
    if case_study:
        normalized["related_case_study"] = case_study

    file = export.generate_xlsx(normalized)
    safe_name = _safe_filename(normalized.get("overview", {}).get("Project Name") or f"project_{project_id}")
    return StreamingResponse(
        file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={safe_name}_{project_id}_preview.xlsx"},
    )


@router.post("/preview/pdf")
async def preview_pdf_from_scope(
    project_id: uuid.UUID,
    scope: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(current_active_user),
):
    import asyncio
    try:
        logger.info(f"📄 Generating PDF preview for project {project_id}")
        project = await _get_project(project_id, current_user.id, db)
        finalized = await _load_finalized_scope(project)
        normalized = export.generate_json_data(scope or {}) if not finalized else finalized

        # Add case study to preview
        case_study = await _fetch_related_case_study(project_id, db)
        if case_study:
            normalized["related_case_study"] = case_study

        logger.info(f"  - Activities count: {len(normalized.get('activities', []))}")
        logger.info(f"  - Resourcing plan count: {len(normalized.get('resourcing_plan', []))}")
        logger.info(f"  - Has discount: {(normalized.get('discount_percentage') or 0) > 0}")
        logger.info(f"  - Architecture diagram: {normalized.get('architecture_diagram', 'None')}")
        logger.info(f"  - Has case study: {bool(normalized.get('related_case_study'))}")

        # Add timeout protection for PDF generation (60 seconds max)
        try:
            file = await asyncio.wait_for(
                export.generate_pdf(normalized),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            logger.error("❌ PDF generation timed out after 60 seconds!")
            raise HTTPException(
                status_code=504,
                detail="PDF generation timed out. This usually means the architecture diagram is too large or blob storage is slow."
            )

        # Check if file is valid
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        logger.info(f"✅ PDF generated successfully - Size: {file_size} bytes")

        if file_size == 0:
            logger.error("❌ Generated PDF is empty!")
            raise HTTPException(status_code=500, detail="Generated PDF is empty")

        safe_name = _safe_filename(normalized.get("overview", {}).get("Project Name") or f"project_{project_id}")
        return StreamingResponse(
            file,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_{project_id}_preview.pdf"},
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"❌ PDF preview generation failed for project {project_id}: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Error details: {str(e)}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


# FINALIZED EXPORTS

@router.get("/json")
async def export_project_json(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(current_active_user),
):
    project = await _get_project(project_id, current_user.id, db)
    scope = await _ensure_scope(project, db)
    return scope


@router.get("/excel")
async def export_project_excel(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(current_active_user),
):
    project = await _get_project(project_id, current_user.id, db)
    scope = await _ensure_scope(project, db)
    normalized = export.generate_json_data(scope or {})
    file = export.generate_xlsx(normalized)
    safe_name = _safe_filename(project.name or f"project_{project.id}")
    return StreamingResponse(
        file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={safe_name}_{project.id}.xlsx"},
    )


@router.get("/pdf")
async def export_project_pdf(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(current_active_user),
):
    import asyncio
    project = await _get_project(project_id, current_user.id, db)
    scope = await _ensure_scope(project, db)
    normalized = export.generate_json_data(scope or {})

    # Add timeout protection for PDF generation (60 seconds max)
    try:
        file = await asyncio.wait_for(
            export.generate_pdf(normalized),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.error("❌ PDF export timed out after 60 seconds!")
        raise HTTPException(
            status_code=504,
            detail="PDF generation timed out. This usually means the architecture diagram is too large or blob storage is slow."
        )

    safe_name = _safe_filename(project.name or f"project_{project.id}")
    return StreamingResponse(
        file,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_name}_{project.id}.pdf"},
    )
