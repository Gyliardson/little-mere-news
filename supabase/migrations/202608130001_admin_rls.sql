begin;

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.admin_users enable row level security;

drop policy if exists "admin_users_read_own_membership" on public.admin_users;
create policy "admin_users_read_own_membership"
on public.admin_users
for select
to authenticated
using (user_id = auth.uid());

revoke all on table public.admin_users from anon;
revoke all on table public.admin_users from authenticated;
grant select on table public.admin_users to authenticated;

-- Publisher idempotency contract used by Backend-Publisher/main.py.
-- This migration intentionally fails if duplicate source_url rows already exist;
-- production data must be reconciled explicitly rather than silently deleted.
create unique index if not exists news_source_url_key
  on public.news (source_url);

alter table public.news enable row level security;

-- Make table privileges explicit instead of depending on dashboard-created grants.
-- RLS remains the authorization boundary for authenticated mutations.
revoke all on table public.news from anon;
revoke all on table public.news from authenticated;
grant select on table public.news to anon, authenticated;
grant insert, update, delete on table public.news to authenticated;

drop policy if exists "news_public_read" on public.news;
create policy "news_public_read"
on public.news
for select
to anon, authenticated
using (true);

drop policy if exists "news_admin_insert" on public.news;
create policy "news_admin_insert"
on public.news
for insert
to authenticated
with check (
  exists (
    select 1
    from public.admin_users
    where admin_users.user_id = auth.uid()
  )
);

drop policy if exists "news_admin_update" on public.news;
create policy "news_admin_update"
on public.news
for update
to authenticated
using (
  exists (
    select 1
    from public.admin_users
    where admin_users.user_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.admin_users
    where admin_users.user_id = auth.uid()
  )
);

drop policy if exists "news_admin_delete" on public.news;
create policy "news_admin_delete"
on public.news
for delete
to authenticated
using (
  exists (
    select 1
    from public.admin_users
    where admin_users.user_id = auth.uid()
  )
);

commit;
