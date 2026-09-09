-- Codinex Attendance System
-- Migration 002: admin-editable office IPs + Wi-Fi override toggle.
-- Run this in the Supabase SQL editor after 001 (schema.sql) has already
-- been applied.

-- ---------------------------------------------------------------------
-- system_settings
--
-- A single-row settings table (id is always 1) so the office IP list and
-- the Wi-Fi override state can be changed from the admin dashboard
-- without a backend redeploy.
-- ---------------------------------------------------------------------
create table if not exists public.system_settings (
    id                        int primary key default 1,
    office_ips                text[] not null default '{}',
    wifi_override_enabled     boolean not null default false,
    wifi_override_expires_at  timestamptz,
    wifi_override_enabled_by  uuid references public.admins (admin_id),
    wifi_override_enabled_at  timestamptz,
    updated_at                timestamptz not null default now(),
    constraint system_settings_singleton check (id = 1)
);

insert into public.system_settings (id)
values (1)
on conflict (id) do nothing;

alter table public.system_settings enable row level security;
-- No public policies: only the service role (used exclusively by the
-- backend) can read or write this table.

-- ---------------------------------------------------------------------
-- attendance.via_wifi_override
--
-- Tags check-ins that were accepted while the Wi-Fi override was active,
-- so they can be reviewed later rather than trusted the same as a normal
-- on-network check-in.
-- ---------------------------------------------------------------------
alter table public.attendance
    add column if not exists via_wifi_override boolean not null default false;
