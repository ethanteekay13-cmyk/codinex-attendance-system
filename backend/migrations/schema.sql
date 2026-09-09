-- Codinex Attendance System
-- Initial schema migration for Supabase / PostgreSQL.
-- Run this in the Supabase SQL editor, or via the Supabase CLI:
--   supabase db push

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- students
-- ---------------------------------------------------------------------
create table if not exists public.students (
    student_id          uuid primary key default gen_random_uuid(),
    user_id             uuid unique references auth.users (id) on delete cascade,
    registration_number varchar not null unique,
    full_name           varchar not null,
    university_name     varchar not null,
    phone_number        varchar not null,
    email               varchar not null unique,
    photo_url           text,
    status              varchar not null default 'active',
    created_at          timestamptz not null default now()
);

create index if not exists idx_students_status on public.students (status);
create index if not exists idx_students_full_name on public.students (full_name);

-- ---------------------------------------------------------------------
-- attendance
-- ---------------------------------------------------------------------
create table if not exists public.attendance (
    attendance_id  uuid primary key default gen_random_uuid(),
    student_id     uuid not null references public.students (student_id) on delete cascade,
    date           date not null default current_date,
    check_in_time  timestamptz not null default now(),
    status         varchar not null check (status in ('present', 'late', 'absent')),
    device_info    text,
    ip_address     varchar,
    constraint uq_attendance_student_date unique (student_id, date)
);

create index if not exists idx_attendance_date on public.attendance (date);
create index if not exists idx_attendance_student_id on public.attendance (student_id);

-- ---------------------------------------------------------------------
-- qr_sessions
-- ---------------------------------------------------------------------
create table if not exists public.qr_sessions (
    session_id  uuid primary key default gen_random_uuid(),
    token       varchar not null,
    created_at  timestamptz not null default now(),
    expires_at  timestamptz,
    is_active   boolean not null default true
);

create index if not exists idx_qr_sessions_created_at on public.qr_sessions (created_at desc);

-- ---------------------------------------------------------------------
-- admins
-- ---------------------------------------------------------------------
create table if not exists public.admins (
    admin_id   uuid primary key default gen_random_uuid(),
    user_id    uuid not null references auth.users (id) on delete cascade,
    full_name  varchar not null,
    role       varchar not null default 'admin'
);

create index if not exists idx_admins_user_id on public.admins (user_id);

-- ---------------------------------------------------------------------
-- Row Level Security
--
-- The FastAPI backend uses the Supabase service role key for all reads
-- and writes, which bypasses RLS entirely. These policies exist as a
-- defense-in-depth measure in case the anon or authenticated keys are
-- ever used to query these tables directly from a client.
-- ---------------------------------------------------------------------
alter table public.students enable row level security;
alter table public.attendance enable row level security;
alter table public.qr_sessions enable row level security;
alter table public.admins enable row level security;

drop policy if exists "students_select_own" on public.students;
create policy "students_select_own"
    on public.students for select
    using (auth.uid() = user_id);

drop policy if exists "attendance_select_own" on public.attendance;
create policy "attendance_select_own"
    on public.attendance for select
    using (
        student_id in (
            select student_id from public.students where user_id = auth.uid()
        )
    );

-- No public policies are defined for qr_sessions or admins: only the
-- service role (used exclusively by the backend) can read or write them.
