-- Codinex Attendance System
-- Migration 003: admin-editable present/late cutoff times.
-- Run this in the Supabase SQL editor after 001 and 002 have already been
-- applied.

alter table public.system_settings
    add column if not exists present_cutoff_time varchar not null default '09:00';

alter table public.system_settings
    add column if not exists late_cutoff_time varchar not null default '09:30';
