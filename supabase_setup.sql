-- Run in Supabase SQL Editor. Only the app server's service-role client may write.
create table if not exists public.tutorial_submissions (
  id bigint generated always as identity primary key,
  student_id text not null,
  student_name text not null,
  answers jsonb not null,
  submitted_at timestamptz not null default now()
);
alter table public.tutorial_submissions enable row level security;
-- NO policies for anon/authenticated roles: app uses server-only service role.
-- IMPORTANT: keep the SERVICE ROLE key ONLY in Streamlit Cloud secrets; never publish in GitHub.
