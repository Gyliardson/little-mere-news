begin;

create extension if not exists pgcrypto;

create table if not exists public.news (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  source_name text not null,
  source_url text not null,
  title_en text not null,
  title_pt text not null,
  summary_en text not null,
  summary_pt text not null,
  published_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

commit;
