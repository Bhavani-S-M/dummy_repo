-- Migration: Add case study support to knowledge_base_documents table
-- Date: 2025-11-22
-- Description: Adds document_type and case_study_metadata fields to support case study matching

-- Add document_type column (if it doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='knowledge_base_documents'
        AND column_name='document_type'
    ) THEN
        ALTER TABLE knowledge_base_documents
        ADD COLUMN document_type VARCHAR(50) DEFAULT 'general';

        CREATE INDEX IF NOT EXISTS idx_kb_documents_document_type
        ON knowledge_base_documents(document_type);

        RAISE NOTICE 'Added document_type column to knowledge_base_documents';
    ELSE
        RAISE NOTICE 'document_type column already exists';
    END IF;
END $$;

-- Add case_study_metadata column (if it doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='knowledge_base_documents'
        AND column_name='case_study_metadata'
    ) THEN
        ALTER TABLE knowledge_base_documents
        ADD COLUMN case_study_metadata TEXT NULL;

        RAISE NOTICE 'Added case_study_metadata column to knowledge_base_documents';
    ELSE
        RAISE NOTICE 'case_study_metadata column already exists';
    END IF;
END $$;

-- Update existing documents to have document_type='general' if NULL
UPDATE knowledge_base_documents
SET document_type = 'general'
WHERE document_type IS NULL;

RAISE NOTICE 'Migration completed successfully!';
