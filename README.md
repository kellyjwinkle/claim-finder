# Claim Finder

A private, household-scale tool for discovering, verifying, and tracking class-action
and mass-settlement claim opportunities. It **never auto-submits legal declarations**.
Every claim requires human review and manual click-to-submit on the official
settlement/administrator site.

## What this does

1. Discovers potential settlements from web research (run by you or a scheduled job).
2. Verifies whether a settlement listing has real official-source indicators
   (court name/number, named administrator, official claim URL).
3. Matches settlements against a household eligibility profile you maintain.
4. Tracks supporting evidence (receipts, invoices, notices) referenced from
   Google Drive by file ID -- documents are never copied into the database.
5. Prepares a claim packet (explanation, checklist, pre-filled draft answers,
   official link) for you to review and submit yourself.
6. Tracks deadlines and submission outcomes.

## What this does NOT do

- Does not submit claim forms automatically.
- Does not sign, attest, or check "under penalty of perjury" boxes for you.
- Does not solve CAPTCHAs or bypass identity verification.
- Does not pay any fee to "file" a claim (legitimate claims are free).
- Does not decide legal eligibility -- it surfaces a transparent, rule-based
  match score and explanation for you to confirm.

## Architecture

```
GitHub Actions (scheduled) --> discovery + verification + deadline checks
        |
        v
   Supabase (Postgres + RLS) --> settlements, eligibility, matches, evidence, audit
        |
        v
   Streamlit app --> review dashboard, evidence vault, claim review, audit log
        |
        v
   Google Drive --> private evidence folder (receipts, notices, confirmations)
```

## Setup

1. Create a Supabase project. Run the SQL in `supabase/migrations/001_initial_schema.sql`,
   then `supabase/policies/rls_policies.sql`.
2. Create a private Google Drive folder for evidence. Note its folder ID.
3. Copy `.env.example` to `.env` (local) or set the same names as Streamlit secrets /
   GitHub Actions secrets. Never commit real secrets.
4. Install dependencies: `pip install -r requirements.txt`
5. Run locally: `streamlit run app/Home.py`
6. Configure the GitHub Actions workflow secrets to enable scheduled discovery
   (`.github/workflows/settlement_monitor.yml`).

## Safety rules baked into the design

- Every settlement starts as `needs_verification` until it has a court/case number
  or official administrator link on file.
- `claim_drafts.ready_for_manual_submission` must be explicitly set by a human
  reviewer in the Streamlit UI -- nothing else flips it to true.
- `claim_submissions` is populated only after you tell the tool you submitted
  the claim yourself (confirmation number / confirmation doc).
- No table stores full account numbers, SSNs, or payment credentials. Use the
  masked-value convention (e.g. `****4821`).
- The redaction helper masks sensitive fields before anything is logged.

## Roadmap

- Phase 1 (this scaffold): discovery queue, verification, eligibility profile,
  evidence catalog, rule-based matching, claim review, manual submission log,
  deadline alerts.
- Phase 2: OCR/text extraction from Drive evidence, vendor-name normalization.
- Phase 3: assisted (not autonomous) browser form-filling that pauses before
  any attestation, signature, or submit action.
