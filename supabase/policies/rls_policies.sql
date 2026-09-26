-- Claim Finder: Row Level Security policies
-- Enable RLS on every exposed table and require ownership through household_members.user_id.

alter table public.household_members enable row level security;
alter table public.settlements enable row level security;
alter table public.settlement_sources enable row level security;
alter table public.eligibility_profiles enable row level security;
alter table public.evidence enable row level security;
alter table public.eligibility_matches enable row level security;
alter table public.match_evidence enable row level security;
alter table public.claim_drafts enable row level security;
alter table public.claim_submissions enable row level security;
alter table public.audit_events enable row level security;

create policy household_members_select on public.household_members
  for select using (auth.uid() = user_id);
create policy household_members_insert on public.household_members
  for insert with check (auth.uid() = user_id);
create policy household_members_update on public.household_members
  for update using (auth.uid() = user_id);
create policy household_members_delete on public.household_members
  for delete using (auth.uid() = user_id);

create policy settlements_select on public.settlements
  for select using (auth.role() = 'authenticated');
create policy settlements_service_write on public.settlements
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy settlement_sources_select on public.settlement_sources
  for select using (auth.role() = 'authenticated');
create policy settlement_sources_service_write on public.settlement_sources
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy eligibility_profiles_select on public.eligibility_profiles
  for select using (
    exists (
      select 1 from public.household_members hm
      where hm.id = eligibility_profiles.household_member_id
        and hm.user_id = auth.uid()
    )
  );
create policy eligibility_profiles_write on public.eligibility_profiles
  for all using (
    exists (
      select 1 from public.household_members hm
      where hm.id = eligibility_profiles.household_member_id
        and hm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.household_members hm
      where hm.id = eligibility_profiles.household_member_id
        and hm.user_id = auth.uid()
    )
  );

create policy evidence_select on public.evidence
  for select using (
    exists (
      select 1 from public.household_members hm
      where hm.id = evidence.household_member_id
        and hm.user_id = auth.uid()
    )
  );
create policy evidence_write on public.evidence
  for all using (
    exists (
      select 1 from public.household_members hm
      where hm.id = evidence.household_member_id
        and hm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.household_members hm
      where hm.id = evidence.household_member_id
        and hm.user_id = auth.uid()
    )
  );

create policy matches_select on public.eligibility_matches
  for select using (
    exists (
      select 1 from public.household_members hm
      where hm.id = eligibility_matches.household_member_id
        and hm.user_id = auth.uid()
    )
  );
create policy matches_write on public.eligibility_matches
  for all using (
    exists (
      select 1 from public.household_members hm
      where hm.id = eligibility_matches.household_member_id
        and hm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.household_members hm
      where hm.id = eligibility_matches.household_member_id
        and hm.user_id = auth.uid()
    )
  );

create policy match_evidence_select on public.match_evidence
  for select using (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = match_evidence.match_id
        and hm.user_id = auth.uid()
    )
  );
create policy match_evidence_write on public.match_evidence
  for all using (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = match_evidence.match_id
        and hm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = match_evidence.match_id
        and hm.user_id = auth.uid()
    )
  );

create policy claim_drafts_select on public.claim_drafts
  for select using (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = claim_drafts.match_id
        and hm.user_id = auth.uid()
    )
  );
create policy claim_drafts_write on public.claim_drafts
  for all using (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = claim_drafts.match_id
        and hm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = claim_drafts.match_id
        and hm.user_id = auth.uid()
    )
  );

create policy claim_submissions_select on public.claim_submissions
  for select using (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = claim_submissions.match_id
        and hm.user_id = auth.uid()
    )
  );
create policy claim_submissions_write on public.claim_submissions
  for all using (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = claim_submissions.match_id
        and hm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.eligibility_matches m
      join public.household_members hm on hm.id = m.household_member_id
      where m.id = claim_submissions.match_id
        and hm.user_id = auth.uid()
    )
  );

create policy audit_events_select on public.audit_events
  for select using (auth.uid() = actor_user_id);
create policy audit_events_insert on public.audit_events
  for insert with check (auth.uid() = actor_user_id or auth.role() = 'service_role');
