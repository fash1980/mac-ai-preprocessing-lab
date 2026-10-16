-- Run in the EXISTING MAC-AI-Preprocessing Supabase project (SQL Editor).
-- Independent of existing tutorial_submissions table.
create table if not exists public.practical_submissions (
 id bigint generated always as identity primary key,
 submission_id text not null unique,
 student_id text not null,
 student_name text not null,
 task_name text not null,
 run_token text not null,
 analysis text not null,
 evidence_paths jsonb not null,
 submitted_at timestamptz not null default now()
);
alter table public.practical_submissions enable row level security;
-- No client-side RLS policies; only server-side service-role access.
insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('practical-evidence','practical-evidence',false,4194304,array['image/png','image/jpeg'])
on conflict (id) do nothing;
-- Private bucket. No anonymous download/upload policies. All access through app server.
