\set ON_ERROR_STOP on

create role anon nologin;
create role authenticated nologin;

create schema auth;
create table auth.users (
  id uuid primary key
);

create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;

\ir ../migrations/202608130000_news_schema.sql
\ir ../migrations/202608130001_admin_rls.sql

insert into auth.users (id) values
  ('00000000-0000-0000-0000-000000000101'),
  ('00000000-0000-0000-0000-000000000202');

insert into public.admin_users (user_id)
values ('00000000-0000-0000-0000-000000000202');

insert into public.news (
  category, source_name, source_url, title_en, title_pt, summary_en, summary_pt
) values (
  'technology', 'fixture', 'https://example.test/public-read',
  'Public read fixture', 'Fixture de leitura', 'Summary', 'Resumo'
);

-- Anonymous users can read but cannot write.
set role anon;
do $$
declare
  visible_count integer;
begin
  select count(*) into visible_count from public.news;
  if visible_count <> 1 then
    raise exception 'anonymous user expected 1 visible row, got %', visible_count;
  end if;

  begin
    insert into public.news (
      category, source_name, source_url, title_en, title_pt, summary_en, summary_pt
    ) values (
      'technology', 'anon', 'https://example.test/anon-write',
      'Denied', 'Negado', 'Denied', 'Negado'
    );
    raise exception 'anonymous insert unexpectedly succeeded';
  exception
    when insufficient_privilege then null;
  end;
end
$$;
reset role;

-- Ordinary authenticated users can read, but RLS blocks mutations.
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000101', false);
do $$
declare
  visible_count integer;
begin
  select count(*) into visible_count from public.news;
  if visible_count <> 1 then
    raise exception 'ordinary user expected 1 visible row, got %', visible_count;
  end if;

  begin
    insert into public.news (
      category, source_name, source_url, title_en, title_pt, summary_en, summary_pt
    ) values (
      'technology', 'regular-user', 'https://example.test/regular-write',
      'Denied', 'Negado', 'Denied', 'Negado'
    );
    raise exception 'ordinary authenticated insert unexpectedly succeeded';
  exception
    when insufficient_privilege then null;
  end;

  begin
    insert into public.admin_users (user_id)
    values ('00000000-0000-0000-0000-000000000101');
    raise exception 'ordinary user unexpectedly created admin membership';
  exception
    when insufficient_privilege then null;
  end;
end
$$;
reset role;

-- An authenticated user with durable admin membership may mutate news.
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000202', false);
insert into public.news (
  category, source_name, source_url, title_en, title_pt, summary_en, summary_pt
) values (
  'technology', 'admin', 'https://example.test/admin-write',
  'Allowed', 'Permitido', 'Allowed', 'Permitido'
);
update public.news
set title_en = 'Updated by admin'
where source_url = 'https://example.test/admin-write';
delete from public.news
where source_url = 'https://example.test/admin-write';
reset role;

-- Publisher idempotency is backed by a database uniqueness constraint.
do $$
begin
  begin
    insert into public.news (
      category, source_name, source_url, title_en, title_pt, summary_en, summary_pt
    ) values (
      'technology', 'duplicate', 'https://example.test/public-read',
      'Duplicate', 'Duplicado', 'Duplicate', 'Duplicado'
    );
    raise exception 'duplicate source_url unexpectedly succeeded';
  exception
    when unique_violation then null;
  end;
end
$$;

select 'RLS contract verified successfully' as result;
