-- Claim Finder: switch from Supabase Auth identity to a single shared
-- household password gate. Drop the foreign keys to auth.users since there
-- are no longer real per-person Supabase Auth accounts driving RLS.
alter table public.household_members
  drop constraint if exists household_members_user_id_fkey;

alter table public.audit_events
  drop constraint if exists audit_events_actor_user_id_fkey;
