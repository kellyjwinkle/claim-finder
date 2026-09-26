-- Claim Finder: Phase 2 -- OCR/extraction fields for evidence
alter table public.evidence
  add column if not exists extracted_text text,
  add column if not exists normalized_merchant text,
  add column if not exists ocr_processed_at timestamptz;

create index if not exists idx_evidence_normalized_merchant
  on public.evidence(normalized_merchant);
