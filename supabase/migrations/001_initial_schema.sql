-- Claim Finder: initial schema
create extension if not exists "pgcrypto";

create type settlement_status as enum (
  'discovered',
  'needs_verification',
  'verified',
  'watching',
  'closed',
  'archived'
);

create type match_status as enum (
  'unreviewed',
  'possible',
  'evidence_needed',
  'ready_for_review',
  'not_eligible',
  'submitted',
  'denied',
  'paid'
);

create type evidence_type as enum (
  'receipt',
  'invoice',
  'order_confirmation',
  'account_statement',
  'claim_notice',
  'email',
  'screenshot',
  'submission_confirmation',
  'other'
);

create table public.household_members (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  display_name text not null,
  relationship text,
  email text,
  phone text,
  created_at timestamptz not null default now()
);

create table public.settlements (
  id uuid primary key default gen_random_uuid(),
  case_name text not null,
  defendant text,
  court text,
  case_number text,
  administrator text,
  official_claim_url text,
  official_notice_url text,
  official_site_url text,
  claim_deadline date,
  exclusion_deadline date,
  objection_deadline date,
  class_period_start date,
  class_period_end date,
  class_definition text,
  geographic_scope text,
  proof_requirements text,
  payment_description text,
  estimated_payment_low numeric(12,2),
  estimated_payment_high numeric(12,2),
  status settlement_status not null default 'discovered',
  verification_notes text,
  last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.settlement_sources (
  id uuid primary key default gen_random_uuid(),
  settlement_id uuid not null references public.settlements(id) on delete cascade,
  source_type text not null check (
    source_type in ('official_administrator', 'court_notice', 'government', 'discovery', 'news')
  ),
  source_url text not null,
  source_title text,
  captured_at timestamptz not null default now(),
  content_hash text,
  is_official boolean not null default false,
  notes text
);

create table public.eligibility_profiles (
  id uuid primary key default gen_random_uuid(),
  household_member_id uuid not null references public.household_members(id) on delete cascade,
  category text not null,
  entity_name text not null,
  account_reference_masked text,
  start_date date,
  end_date date,
  state_or_region text,
  notes text,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.evidence (
  id uuid primary key default gen_random_uuid(),
  household_member_id uuid not null references public.household_members(id) on delete cascade,
  evidence_type evidence_type not null,
  title text not null,
  merchant_or_service text,
  document_date date,
  period_start date,
  period_end date,
  drive_file_id text not null,
  drive_web_url text,
  contains_sensitive_data boolean not null default false,
  checksum text,
  notes text,
  created_at timestamptz not null default now()
);

create table public.eligibility_matches (
  id uuid primary key default gen_random_uuid(),
  settlement_id uuid not null references public.settlements(id) on delete cascade,
  household_member_id uuid not null references public.household_members(id) on delete cascade,
  status match_status not null default 'unreviewed',
  confidence_score integer not null default 0 check (confidence_score between 0 and 100),
  match_explanation text not null,
  missing_information text,
  reviewer_notes text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(settlement_id, household_member_id)
);

create table public.match_evidence (
  match_id uuid not null references public.eligibility_matches(id) on delete cascade,
  evidence_id uuid not null references public.evidence(id) on delete cascade,
  relevance_note text,
  primary key (match_id, evidence_id)
);

create table public.claim_drafts (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null unique references public.eligibility_matches(id) on delete cascade,
  official_claim_url text not null,
  prepared_answers jsonb not null default '{}'::jsonb,
  checklist jsonb not null default '[]'::jsonb,
  user_reviewed_at timestamptz,
  ready_for_manual_submission boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.claim_submissions (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null unique references public.eligibility_matches(id) on delete cascade,
  submitted_by_member_id uuid not null references public.household_members(id),
  submitted_at timestamptz not null,
  confirmation_number text,
  confirmation_drive_file_id text,
  submission_notes text,
  outcome text check (outcome in ('submitted', 'approved', 'denied', 'paid', 'unknown')),
  payment_amount numeric(12,2),
  payment_date date,
  created_at timestamptz not null default now()
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid references auth.users(id),
  event_type text not null,
  entity_type text not null,
  entity_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index idx_settlements_status on public.settlements(status);
create index idx_settlements_deadline on public.settlements(claim_deadline);
create index idx_matches_status on public.eligibility_matches(status);
create index idx_evidence_member on public.evidence(household_member_id);
