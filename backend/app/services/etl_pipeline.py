"""
ETL Pipeline Service for Knowledge Base Documents

This service monitors Azure Blob Storage for new knowledge base documents,
converts them to vectors, stores in Qdrant, and manages admin approvals for updates.

Architecture:
1. Monitor blob storage for new uploads
2. Extract text and chunk documents
3. Generate embeddings using Ollama
4. Check similarity with existing KB documents
5. Create pending approval if updates detected
6. Store vectors in Qdrant after admin approval
"""

import asyncio
import hashlib
import json
import logging
import io
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import models as models_qdrant

from app import models
from app.utils import azure_blob
from app.utils.scope_engine import extract_text_from_file
from app.utils.ai_clients import embed_text_ollama, get_qdrant_client
from app.utils.case_study_parser import parse_case_study_from_ppt, extract_all_text_from_ppt
from app.config.config import QDRANT_COLLECTION, CASE_STUDY_COLLECTION

logger = logging.getLogger(__name__)


class ETLPipeline:
    """ETL Pipeline for Knowledge Base documents."""

    def __init__(self):
        self.qdrant_client = get_qdrant_client()
        self.chunk_size = 1000  # Characters per chunk
        self.overlap = 200  # Overlap between chunks
        self.similarity_threshold = 0.85  # Threshold for detecting updates

    def _is_case_study_document(self, blob_path: str, file_name: str) -> bool:
        """
        Determine if a document is a case study based on path or filename.

        Detection criteria:
        - Folder path contains "case_study" or "case study"
        - Filename contains "case_study" or "case study"
        - Filename matches pattern like "CS_*.pptx"
        """
        path_lower = blob_path.lower()
        name_lower = file_name.lower()

        # Check folder path
        if any(keyword in path_lower for keyword in ["case_study", "case study", "casestudy"]):
            return True

        # Check filename
        if any(keyword in name_lower for keyword in ["case_study", "case study", "casestudy", "client_story"]):
            return True

        # Check for common case study filename patterns
        if name_lower.startswith("cs_") or name_lower.startswith("case_"):
            return True

        return False

    async def scan_and_process_new_documents(self, db: AsyncSession) -> Dict[str, int]:
        """
        Scan blob storage for new KB documents and process them.

        Returns:
            Dict with counts of new, updated, and failed documents
        """
        logger.info("🔍 Starting ETL scan for new KB documents...")

        stats = {
            "scanned": 0,
            "new": 0,
            "updated": 0,
            "failed": 0,
            "pending_approval": 0
        }

        try:
            # List all documents in knowledge_base blob storage
            tree = await azure_blob.explorer("knowledge_base")
            all_files = self._flatten_tree(tree)
            stats["scanned"] = len(all_files)

            logger.info(f"📄 Found {len(all_files)} files in knowledge_base storage")

            for file_info in all_files:
                try:
                    await self._process_single_document(db, file_info, stats)
                except Exception as e:
                    logger.error(f"❌ Failed to process {file_info['name']}: {e}")
                    stats["failed"] += 1

            await db.commit()

            logger.info(f"✅ ETL scan completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"❌ ETL scan failed: {e}")
            await db.rollback()
            raise

    async def _process_single_document(
        self,
        db: AsyncSession,
        file_info: Dict,
        stats: Dict
    ) -> None:
        """Process a single document through the ETL pipeline."""

        blob_path = file_info["path"]
        file_name = file_info["name"]

        # Download document and calculate hash
        try:
            file_bytes = await azure_blob.download_bytes(blob_path, "knowledge_base")
        except Exception as e:
            logger.warning(f"⚠️ Could not download {blob_path}: {e}")
            return

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)

        # Check if document already exists
        result = await db.execute(
            select(models.KnowledgeBaseDocument).where(
                models.KnowledgeBaseDocument.blob_path == blob_path
            )
        )
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            # Check if file has changed
            if existing_doc.file_hash == file_hash:
                # File hasn't changed, but check if it needs reprocessing
                if existing_doc.is_vectorized:
                    logger.debug(f"⏭️  Skipping unchanged document: {file_name}")
                    return
                else:
                    # Check if document already has a pending approval
                    pending_check = await db.execute(
                        select(models.PendingKBUpdate).where(
                            and_(
                                models.PendingKBUpdate.new_document_id == existing_doc.id,
                                models.PendingKBUpdate.status == "pending"
                            )
                        ).limit(1)
                    )
                    has_pending_approval = pending_check.first() is not None

                    if has_pending_approval:
                        logger.debug(f"⏭️  Skipping document with pending approval: {file_name}")
                        return

                    # Document exists but not vectorized (failed or reset) - reprocess it
                    logger.info(f"🔄 Reprocessing failed/reset document: {file_name}")
                    existing_doc.last_checked = datetime.now(timezone.utc)
                    doc = existing_doc
                    stats["updated"] += 1
            else:
                logger.info(f"🔄 Document changed: {file_name}")
                # Update existing record
                existing_doc.file_hash = file_hash
                existing_doc.file_size = file_size
                existing_doc.is_vectorized = False
                existing_doc.last_checked = datetime.now(timezone.utc)
                doc = existing_doc
                stats["updated"] += 1
        else:
            # Detect if this is a case study document
            is_case_study = self._is_case_study_document(blob_path, file_name)
            doc_type = "case_study" if is_case_study else "general"

            # Create new document record
            doc = models.KnowledgeBaseDocument(
                file_name=file_name,
                blob_path=blob_path,
                file_hash=file_hash,
                file_size=file_size,
                is_vectorized=False,
                document_type=doc_type
            )
            db.add(doc)
            await db.flush()  # Get the document ID
            stats["new"] += 1
            logger.info(f"📝 New {doc_type} document added: {file_name}")

        # Extract text from document
        try:
            # For case study PPTs, try structured parsing first
            if doc.document_type == "case_study" and file_name.lower().endswith(('.ppt', '.pptx')):
                # Save file temporarily for parsing
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
                    tmp_file.write(file_bytes)
                    tmp_path = tmp_file.name

                try:
                    # Parse structured case study data
                    case_studies = parse_case_study_from_ppt(tmp_path)

                    if case_studies and len(case_studies) > 0:
                        logger.info(f"📚 Found {len(case_studies)} case studies in {file_name}")

                        # Process each case study separately
                        for idx, case_study in enumerate(case_studies):
                            # For first case study, use existing doc record
                            # For additional ones, create new document records
                            if idx == 0:
                                current_doc = doc
                            else:
                                # Create unique identifier for additional case studies
                                case_study_blob_path = f"{blob_path}#case_study_{idx + 1}"
                                client_name = case_study.get('client_name', f'Case Study {idx + 1}')
                                case_study_file_name = f"{file_name} - {client_name}"

                                # Check if this specific case study already exists
                                result = await db.execute(
                                    select(models.KnowledgeBaseDocument).where(
                                        models.KnowledgeBaseDocument.blob_path == case_study_blob_path
                                    )
                                )
                                existing_case_doc = result.scalar_one_or_none()

                                if existing_case_doc:
                                    # Update existing case study document
                                    existing_case_doc.file_hash = file_hash
                                    existing_case_doc.file_size = file_size
                                    existing_case_doc.is_vectorized = False
                                    existing_case_doc.last_checked = datetime.now(timezone.utc)
                                    current_doc = existing_case_doc
                                    logger.info(f"🔄 Updating existing case study: {client_name}")
                                else:
                                    # Create new document record for this case study
                                    current_doc = models.KnowledgeBaseDocument(
                                        file_name=case_study_file_name,
                                        blob_path=case_study_blob_path,
                                        file_hash=file_hash,
                                        file_size=file_size,
                                        is_vectorized=False,
                                        document_type="case_study"
                                    )
                                    db.add(current_doc)
                                    await db.flush()
                                    logger.info(f"📝 Created new case study document: {client_name}")

                            # Store metadata for this specific case study
                            current_doc.case_study_metadata = json.dumps({
                                "client_name": case_study.get("client_name", ""),
                                "overview": case_study.get("overview", ""),
                                "solution": case_study.get("solution", ""),
                                "impact": case_study.get("impact", ""),
                                "slide_range": case_study.get("slide_range", "")
                            })

                            case_text_content = case_study.get("full_text", "")

                            if case_text_content and len(case_text_content.strip()) >= 50:
                                # Vectorize and store this case study
                                await self._vectorize_and_store(db, current_doc, case_text_content)
                                logger.info(f"✅ Case study vectorized: {case_study.get('client_name', 'Unknown')}")
                            else:
                                logger.warning(f"⚠️ Insufficient text for case study: {case_study.get('client_name', 'Unknown')}")

                        # Cleanup: Remove orphaned case study documents
                        # If file previously had more case studies than now, delete the extras
                        orphan_check_idx = len(case_studies) + 1
                        while True:
                            orphan_blob_path = f"{blob_path}#case_study_{orphan_check_idx}"
                            result = await db.execute(
                                select(models.KnowledgeBaseDocument).where(
                                    models.KnowledgeBaseDocument.blob_path == orphan_blob_path
                                )
                            )
                            orphan_doc = result.scalar_one_or_none()

                            if orphan_doc:
                                logger.info(f"🗑️  Removing orphaned case study document: {orphan_doc.file_name}")
                                # Delete from Qdrant first
                                try:
                                    self.qdrant_client.delete(
                                        collection_name=CASE_STUDY_COLLECTION,
                                        points_selector=models_qdrant.FilterSelector(
                                            filter=models_qdrant.Filter(
                                                must=[
                                                    models_qdrant.FieldCondition(
                                                        key="document_id",
                                                        match=models_qdrant.MatchValue(value=str(orphan_doc.id))
                                                    )
                                                ]
                                            )
                                        )
                                    )
                                except Exception as e:
                                    logger.warning(f"⚠️ Failed to delete vectors for orphaned case study: {e}")

                                # Delete from database
                                await db.delete(orphan_doc)
                                orphan_check_idx += 1
                            else:
                                # No more orphaned documents found
                                break

                        # All case studies processed, return early
                        return
                    else:
                        # Fallback to full text extraction
                        text_content = extract_all_text_from_ppt(tmp_path)
                        logger.warning(f"⚠️ Structured parsing failed, using full text extraction")
                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            else:
                # Standard text extraction for non-case-study documents
                text_content = extract_text_from_file(io.BytesIO(file_bytes), file_name)

            if not text_content or len(text_content.strip()) < 50:
                logger.warning(f"⚠️ No meaningful text extracted from {file_name}")
                return
        except Exception as e:
            logger.error(f"❌ Text extraction failed for {file_name}: {e}")
            return

        # Check for similar existing documents
        similar_docs = await self._find_similar_documents(db, text_content, doc.id)

        if similar_docs:
            # Create pending approval for admin review
            await self._create_pending_approval(db, doc, similar_docs, text_content)
            stats["pending_approval"] += 1
            logger.info(f"⏸️  Pending admin approval for {file_name} (found {len(similar_docs)} similar docs)")
        else:
            # No similar documents, proceed with vectorization
            await self._vectorize_and_store(db, doc, text_content)
            logger.info(f"✅ Document vectorized: {file_name}")

    async def _find_similar_documents(
        self,
        db: AsyncSession,
        text_content: str,
        exclude_doc_id: str
    ) -> List[Dict]:
        """
        Find existing KB documents similar to the new content.

        NOTE: This only searches within KB documents, NOT case studies.
        Case studies have their own separate collection and are not mixed with KB.

        Returns:
            List of similar documents with similarity scores
        """
        try:
            # Generate embedding for the document
            sample_text = text_content[:2000]  # Use first 2000 chars for comparison
            embeddings = embed_text_ollama([sample_text])

            if not embeddings or not embeddings[0]:
                return []

            query_vector = embeddings[0]

            # Search Qdrant for similar vectors (KB collection only, no case studies)
            search_results = self.qdrant_client.search(
                collection_name=QDRANT_COLLECTION,  # Only search KB documents
                query_vector=query_vector,
                limit=5,
                score_threshold=self.similarity_threshold
            )

            if not search_results:
                return []

            similar_docs = []
            for hit in search_results:
                payload = hit.payload or {}
                doc_id = payload.get("document_id")

                if doc_id and doc_id != str(exclude_doc_id):
                    # Get document details from DB
                    result = await db.execute(
                        select(models.KnowledgeBaseDocument).where(
                            models.KnowledgeBaseDocument.id == doc_id
                        )
                    )
                    doc = result.scalar_one_or_none()

                    if doc:
                        similar_docs.append({
                            "document_id": str(doc.id),
                            "file_name": doc.file_name,
                            "similarity_score": float(hit.score),
                            "blob_path": doc.blob_path
                        })

            return similar_docs

        except Exception as e:
            logger.warning(f"⚠️ Similarity check failed: {e}")
            return []

    async def _create_pending_approval(
        self,
        db: AsyncSession,
        doc: models.KnowledgeBaseDocument,
        similar_docs: List[Dict],
        text_content: str
    ) -> None:
        """Create a pending KB update for admin approval."""

        # Determine update type
        max_similarity = max(d["similarity_score"] for d in similar_docs)

        if max_similarity > 0.95:
            update_type = "duplicate"
            reason = f"Very high similarity ({max_similarity:.2%}) with existing document(s)"
        elif max_similarity > self.similarity_threshold:
            update_type = "update"
            reason = f"High similarity ({max_similarity:.2%}) - possible update to existing content"
        else:
            update_type = "new"
            reason = "New document with some related content"

        pending = models.PendingKBUpdate(
            new_document_id=doc.id,
            related_documents=json.dumps(similar_docs),
            update_type=update_type,
            similarity_score=max_similarity,
            reason=reason,
            status="pending"
        )
        db.add(pending)

        logger.info(f"📋 Created pending approval: {update_type} - {doc.file_name}")

    async def _vectorize_and_store(
        self,
        db: AsyncSession,
        doc: models.KnowledgeBaseDocument,
        text_content: str
    ) -> None:
        """
        Chunk the document, generate embeddings, and store in Qdrant.
        """
        # Create processing job
        job = models.DocumentProcessingJob(
            document_id=doc.id,
            status="processing",
            started_at=datetime.now(timezone.utc)
        )
        db.add(job)
        await db.flush()

        try:
            # Chunk the text
            chunks = self._chunk_text(text_content)
            job.chunks_processed = len(chunks)

            # Generate embeddings for all chunks
            embeddings = embed_text_ollama(chunks)

            if not embeddings or len(embeddings) != len(chunks):
                raise ValueError(f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}")

            # Store vectors in Qdrant
            from qdrant_client.http import models as qdrant_models

            points = []
            for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
                # Convert UUID + index to stable integer ID for Qdrant
                # Qdrant requires pure integers or pure UUIDs, not concatenated strings
                point_id_str = f"{doc.id}_{idx}"
                point_id = int(hashlib.sha256(point_id_str.encode()).hexdigest()[:16], 16)

                payload = {
                    "document_id": str(doc.id),
                    "file_name": doc.file_name,
                    "blob_path": doc.blob_path,
                    "chunk_index": idx,
                    "content": chunk[:1000],  # Store first 1000 chars
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "document_type": doc.document_type or "general"
                }

                # Add case study metadata to payload if available
                if doc.document_type == "case_study" and doc.case_study_metadata:
                    payload["case_study_metadata"] = doc.case_study_metadata

                points.append(
                    qdrant_models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                )

            # Route to correct collection based on document type
            if doc.document_type == "case_study":
                target_collection = CASE_STUDY_COLLECTION
                logger.info(f"📚 Storing case study in separate collection: {CASE_STUDY_COLLECTION}")
            else:
                target_collection = QDRANT_COLLECTION
                logger.debug(f"📄 Storing KB document in collection: {QDRANT_COLLECTION}")

            # Upload to Qdrant
            self.qdrant_client.upsert(
                collection_name=target_collection,
                points=points
            )

            # Update document record
            doc.is_vectorized = True
            doc.vectorized_at = datetime.now(timezone.utc)
            doc.vector_count = len(points)
            # Store point IDs as integers (not strings)
            doc.qdrant_point_ids = json.dumps([int(p.id) for p in points])

            # Update job status
            job.status = "completed"
            job.vectors_created = len(points)
            job.completed_at = datetime.now(timezone.utc)

            logger.info(f"✅ Vectorized {doc.file_name}: {len(points)} vectors created in '{target_collection}' collection")

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            logger.error(f"❌ Vectorization failed for {doc.file_name}: {e}")
            raise

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('. ')
                if last_period > self.chunk_size * 0.7:  # At least 70% of chunk size
                    end = start + last_period + 1
                    chunk = text[start:end]

            chunks.append(chunk.strip())
            start = end - self.overlap  # Overlap with next chunk

        return [c for c in chunks if c]  # Remove empty chunks

    def _flatten_tree(self, tree: Dict) -> List[Dict]:
        """Flatten the blob explorer tree into a list of files."""
        files = []

        def traverse(node, path=""):
            # Check if this is a file (not a folder)
            if node.get("is_folder") is False:
                files.append({
                    "name": node["name"],
                    "path": node.get("path", f"{path}/{node['name']}".lstrip("/"))
                })
            # If it has children (is a folder), traverse them
            if node.get("children"):
                for child in node["children"]:
                    child_path = f"{path}/{node['name']}".lstrip("/") if node.get("name") else path
                    traverse(child, child_path)

        traverse(tree)
        return files

    async def approve_and_process(
        self,
        db: AsyncSession,
        pending_update_id: str,
        admin_user_id: str,
        admin_comment: Optional[str] = None
    ) -> Dict:
        """
        Admin approves a pending KB update and processes the document.

        Returns:
            Status dictionary with processing results
        """
        result = await db.execute(
            select(models.PendingKBUpdate).where(
                models.PendingKBUpdate.id == pending_update_id
            )
        )
        pending = result.scalar_one_or_none()

        if not pending:
            raise ValueError(f"Pending update {pending_update_id} not found")

        if pending.status != "pending":
            raise ValueError(f"Update already {pending.status}")

        # Get the document
        doc_result = await db.execute(
            select(models.KnowledgeBaseDocument).where(
                models.KnowledgeBaseDocument.id == pending.new_document_id
            )
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            raise ValueError(f"Document {pending.new_document_id} not found")

        # Update approval status
        pending.status = "approved"
        pending.reviewed_by = admin_user_id
        pending.reviewed_at = datetime.now(timezone.utc)
        pending.admin_comment = admin_comment

        # Download and process the document
        try:
            file_bytes = await azure_blob.download_bytes(doc.blob_path, "knowledge_base")
            text_content = extract_text_from_file(io.BytesIO(file_bytes), doc.file_name)

            # Vectorize and store
            await self._vectorize_and_store(db, doc, text_content)
            await db.commit()

            logger.info(f"✅ Approved and processed: {doc.file_name}")

            return {
                "status": "success",
                "document_id": str(doc.id),
                "file_name": doc.file_name,
                "vectors_created": doc.vector_count
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to process approved document: {e}")
            raise

    async def reject_update(
        self,
        db: AsyncSession,
        pending_update_id: str,
        admin_user_id: str,
        admin_comment: Optional[str] = None
    ) -> Dict:
        """Admin rejects a pending KB update."""

        result = await db.execute(
            select(models.PendingKBUpdate).where(
                models.PendingKBUpdate.id == pending_update_id
            )
        )
        pending = result.scalar_one_or_none()

        if not pending:
            raise ValueError(f"Pending update {pending_update_id} not found")

        if pending.status != "pending":
            raise ValueError(f"Update already {pending.status}")

        # Update rejection status
        pending.status = "rejected"
        pending.reviewed_by = admin_user_id
        pending.reviewed_at = datetime.now(timezone.utc)
        pending.admin_comment = admin_comment

        await db.commit()

        logger.info(f"❌ Rejected KB update: {pending_update_id}")

        return {
            "status": "rejected",
            "pending_update_id": str(pending.id)
        }


# Global ETL pipeline instance
_etl_pipeline = None

def get_etl_pipeline() -> ETLPipeline:
    """Get singleton ETL pipeline instance."""
    global _etl_pipeline
    if _etl_pipeline is None:
        _etl_pipeline = ETLPipeline()
    return _etl_pipeline
