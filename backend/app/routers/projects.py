import uuid, json, logging
from typing import List, Optional, Dict, Any

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form, status
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import schemas, models
from app import crud as projects
from app.config.database import get_async_session
from app.utils import scope_engine, azure_blob
from app.auth.router import fastapi_users

get_current_active_user = fastapi_users.current_user(active=True)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# LIST ALL PROJECTS
@router.get("", response_model=List[schemas.Project])
async def list_projects(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    items = await projects.list_projects(db, owner_id=current_user.id)

    for p in items:
        p.has_finalized_scope = await projects.has_finalized_scope(db, p.id)

        if p.company_id:
            await db.refresh(p, attribute_names=["company"])

    return items


# CREATE PROJECT
@router.post("", response_model=schemas.Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    complexity: Optional[str] = Form(None),
    tech_stack: Optional[str] = Form(None),
    use_cases: Optional[str] = Form(None),
    compliance: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    company_id: Optional[uuid.UUID] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    if not any([name, domain, complexity, tech_stack, use_cases, compliance, duration, files]):
        raise HTTPException(
            status_code=400,
            detail="At least one project field or file must be provided."
        )

    if company_id:
        from app.utils import ratecards
        sigmoid = await ratecards.get_or_create_sigmoid_company(db)
        if company_id != sigmoid.id:
            result = await db.execute(
                select(models.Company).filter(
                    models.Company.id == company_id,
                    models.Company.owner_id == current_user.id,
                )
            )
            company = result.scalar_one_or_none()
            if not company:
                raise HTTPException(
                    status_code=403,
                    detail="You do not own this company."
                )

    project_data = schemas.ProjectCreate(
        name=name.strip() if name else None,
        domain=domain,
        complexity=complexity,
        tech_stack=tech_stack,
        use_cases=use_cases,
        compliance=compliance,
        duration=duration,
        company_id=company_id,
    )

    db_project = await projects.create_project(db, project_data, current_user.id, files)
    db_project.has_finalized_scope = False
    return db_project


# GET PROJECT DETAILS
@router.get("/{project_id}", response_model=schemas.Project)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """Get project details including company and files."""
    project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.refresh(project, attribute_names=["company"])
    project.has_finalized_scope = await projects.has_finalized_scope(db, project.id)
    return project


# UPDATE PROJECT
@router.put("/{project_id}", response_model=schemas.Project)
async def update_project(
    project_id: uuid.UUID,
    project_update: schemas.ProjectBase,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """Update editable fields of a project."""
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    updated = await projects.update_project(db, db_project, project_update)
    await db.refresh(updated, attribute_names=["company"])
    return updated

# DELETE PROJECT
@router.delete("/{project_id}", response_model=schemas.MessageResponse)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """Delete a project. Blob cleanup handled automatically by event listeners."""
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    await projects.delete_project(db, db_project)
    logger.info(f" Deleted project {project_id} (Blob folder auto-cleaned).")

    return {"msg": f"Project {project_id} deleted successfully (DB + Blob auto-cleaned)."}


#  DELETE ALL PROJECTS
@router.delete("", response_model=schemas.MessageResponse)
async def delete_all_projects(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """Delete all projects for the current user (DB + Blob auto cleanup)."""
    count = await projects.delete_all_projects(db, owner_id=current_user.id)
    logger.info(f" Deleted {count} projects for user {current_user.id}.")
    return {"msg": f"Deleted {count} projects successfully (DB + Blob auto-cleaned)."}

# Generate Scope
@router.get("/{project_id}/generate_scope", response_model=schemas.GeneratedScopeResponse)
async def generate_project_scope_route(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    # Fetch the project
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate full scope (includes architecture)
    scope = await scope_engine.generate_project_scope(db, db_project) or {}

    return schemas.GeneratedScopeResponse(
        overview=scope.get("overview", {}),
        activities=scope.get("activities", []),
        resourcing_plan=scope.get("resourcing_plan", []),
        architecture_diagram=scope.get("architecture_diagram")
    )



# Finalize Scope
@router.post("/{project_id}/finalize_scope", response_model=schemas.MessageResponse)
async def finalize_project_scope(
    project_id: uuid.UUID,
    scope_data: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_file, cleaned_scope = await scope_engine.finalize_scope(db, db_project.id, scope_data)
    return {
        "msg": "Project scope finalized successfully",
        "scope": cleaned_scope,
        "file_url": azure_blob.get_blob_url(db_file.file_path),
        "has_finalized_scope": True
    }

# Get Finalized Scope
@router.get("/{project_id}/finalized_scope")
async def get_finalized_scope(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(models.ProjectFile).filter(
            models.ProjectFile.project_id == project_id,
            models.ProjectFile.file_name == "finalized_scope.json"
        )
    )
    db_file = result.scalars().first()

    if not db_file:
        return None 

    try:
        blob_bytes = await azure_blob.download_bytes(db_file.file_path)
        scope_data = json.loads(blob_bytes.decode("utf-8"))
        return scope_data
    except Exception as e:
        logger.error(f"Failed to fetch finalized scope: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch finalized scope")

# ==========================================================
# 🔁 Regenerate Scope with User Instructions
# ==========================================================
@router.post("/{project_id}/regenerate_scope", response_model=schemas.GeneratedScopeResponse)
async def regenerate_scope_with_instructions(
    project_id: uuid.UUID,
    request: schemas.RegenerateScopeRequest,   # ✅ use schema instead of Dict
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Regenerate a project's scope based on user-provided instructions.
    Overwrites finalized_scope.json in Azure Blob + updates DB metadata.
    """
    # Validate project
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Extract data from request model
    draft = request.draft
    instructions = request.instructions or ""

    if not draft:
        raise HTTPException(status_code=400, detail="Missing draft scope payload")

    # Regenerate
    try:
        logger.info(f"Regenerating scope for project {project_id} with instructions: {instructions[:120]}...")
        regen_scope = await scope_engine.regenerate_from_instructions(
            db=db,
            project=db_project,
            draft=draft,
            instructions=instructions,
        )

        # Return structured response
        return schemas.GeneratedScopeResponse(
            overview=regen_scope.get("overview", {}),
            activities=regen_scope.get("activities", []),
            resourcing_plan=regen_scope.get("resourcing_plan", []),
            architecture_diagram=regen_scope.get("architecture_diagram", None),
            discount_percentage=regen_scope.get("discount_percentage", None),
        )

    except Exception as e:
        logger.error(f"Scope regeneration failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Scope regeneration failed")
    

@router.post(
    "/{project_id}/generate_questions",
    response_model=schemas.GenerateQuestionsResponse
)
async def generate_project_questions_route(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    # Fetch project
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Generate categorized questions
        data = await scope_engine.generate_project_questions(db, db_project)
        total_q = sum(len(c["items"]) for c in data.get("questions", []))

        return {
            "msg": f"Generated {total_q} questions successfully",
            "questions": data.get("questions", []),
        }
    except Exception as e:
        logger.error(f"Question generation failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Question generation failed")


# Update Project Questions with User Input
@router.post("/{project_id}/update_questions")
async def update_project_questions_with_answers(
    project_id: uuid.UUID,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Merge user answers into existing questions.json and re-save to Blob + DB.
    Expected payload structure:
    {
      "Architecture": {
        "What is the preferred deployment model?": "Cloud-based",
        "Do you need auto-scaling or load balancing?": "Yes, via AKS"
      },
      "Data & Security": {
        "Will sensitive data be stored or processed?": "Yes, PII data"
      }
    }
    """
    # Fetch project
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    user_answers = payload or {}
    if not user_answers:
        raise HTTPException(status_code=400, detail="Missing user_answers payload")

    try:
        result = await scope_engine.update_questions_with_user_input(db, db_project, user_answers)
        return {
            "msg": "Questions updated successfully with user answers.",
            "updated_questions": result.get("questions", []),
        }
    except Exception as e:
        logger.error(f"Failed to update questions.json for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update questions.json")

# Get Project Questions (from Blob)
@router.get("/{project_id}/questions")
async def get_project_questions(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Fetch the latest questions.json for a project from Azure Blob Storage.
    Returns the same structure used by generate_questions.
    """
    # Fetch project
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    blob_name = f"projects/{project_id}/questions.json"

    try:
        # Check if blob exists
        if not await azure_blob.blob_exists(blob_name):
            raise HTTPException(status_code=404, detail="questions.json not found for this project")

        # Download the blob content
        q_bytes = await azure_blob.download_bytes(blob_name)
        q_json = json.loads(q_bytes.decode("utf-8"))
        return q_json

    except Exception as e:
        logger.error(f"Failed to fetch questions.json for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project questions")


# GET RELATED CASE STUDY
@router.get("/{project_id}/related_case_study")
async def get_related_case_study(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Find the most relevant case study for a project based on its executive summary.

    Returns:
        - Matched case study with client_name, overview, solution, impact
        - Or message indicating no match was found
    """
    from app.utils.ai_clients import embed_text_ollama, get_qdrant_client
    from app.config.config import CASE_STUDY_COLLECTION

    # Fetch project
    db_project = await projects.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load finalized_scope.json from blob storage
    blob_name = f"projects/{project_id}/finalized_scope.json"

    try:
        # Check if scope exists
        if not await azure_blob.blob_exists(blob_name):
            raise HTTPException(
                status_code=404,
                detail="Project scope not generated yet. Please generate project scope first."
            )

        # Download and parse scope
        scope_bytes = await azure_blob.download_bytes(blob_name)
        scope_data = json.loads(scope_bytes.decode("utf-8"))

        # Extract executive summary from project_summary
        project_summary = scope_data.get("project_summary", {})
        executive_summary = project_summary.get("executive_summary", "")

        if not executive_summary or len(executive_summary.strip()) < 20:
            # Fallback to project overview or description
            overview = scope_data.get("overview", {})
            executive_summary = (
                overview.get("Project Description", "") or
                overview.get("description", "") or
                f"{db_project.tech_stack or ''} {db_project.use_cases or ''}"
            )

        if not executive_summary or len(executive_summary.strip()) < 20:
            raise HTTPException(
                status_code=400,
                detail="Insufficient project description for case study matching. Please ensure project has executive summary."
            )

        logger.info(f"🔍 Finding case study for project {project_id} using executive summary (length: {len(executive_summary)} chars)")

        # Generate embedding from executive summary
        embeddings = embed_text_ollama([executive_summary])
        if not embeddings or not embeddings[0]:
            raise HTTPException(status_code=500, detail="Failed to generate embedding for project summary")

        query_vector = embeddings[0]

        # Search Qdrant in case study collection (separate from KB)
        qdrant_client = get_qdrant_client()

        logger.info(f"📚 Searching for case studies in separate collection: {CASE_STUDY_COLLECTION}")
        search_results = qdrant_client.search(
            collection_name=CASE_STUDY_COLLECTION,  # Dedicated case study collection
            query_vector=query_vector,
            limit=1,
            score_threshold=0.80  # Minimum similarity threshold (increased to ensure better semantic match)
        )

        if not search_results or len(search_results) == 0:
            return {
                "matched": False,
                "message": "No matching case study was found in the provided PPT files.",
                "similarity_score": 0.0
            }

        # Get the best match
        best_match = search_results[0]
        payload = best_match.payload or {}
        similarity_score = float(best_match.score)

        logger.info(f"✅ Found case study match in '{CASE_STUDY_COLLECTION}' collection with similarity: {similarity_score:.2%}")

        # Parse case study metadata from payload
        case_study_json = payload.get("case_study_metadata")
        if case_study_json:
            case_study_data = json.loads(case_study_json) if isinstance(case_study_json, str) else case_study_json
        else:
            # Fallback: get from database
            document_id = payload.get("document_id")
            if document_id:
                result = await db.execute(
                    select(models.KnowledgeBaseDocument).where(
                        models.KnowledgeBaseDocument.id == uuid.UUID(document_id)
                    )
                )
                doc = result.scalar_one_or_none()
                if doc and doc.case_study_metadata:
                    case_study_data = json.loads(doc.case_study_metadata)
                else:
                    case_study_data = {}
            else:
                case_study_data = {}

        # Extract structured fields
        client_name = case_study_data.get("client_name", payload.get("file_name", "Unknown Client"))
        overview = case_study_data.get("overview", payload.get("content", "")[:500])
        solution = case_study_data.get("solution", "")
        impact = case_study_data.get("impact", "")

        return {
            "matched": True,
            "similarity_score": similarity_score,
            "case_study": {
                "client_name": client_name,
                "overview": overview,
                "solution": solution,
                "impact": impact,
                "file_name": payload.get("file_name", ""),
                "slide_range": case_study_data.get("slide_range", "")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find related case study for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find related case study: {str(e)}")

