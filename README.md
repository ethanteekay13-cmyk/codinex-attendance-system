# Codinex Attendance System

Attendance tracking for Codinex Computers Ltd internship students (100-130
students per intake), built with FastAPI, Supabase, and vanilla JavaScript.

## 1. Set up Supabase

1. Create a Supabase project.
2. Open the SQL editor and run `backend/migrations/schema.sql`. This creates
   the `students`, `attendance`, `qr_sessions`, and `admins` tables, plus
   basic row level security policies.
3. Under Project Settings > API, copy the Project URL, the `anon` public
   key, and the `service_role` key.
4. Under Project Settings > API > JWT Settings, copy the JWT Secret.

## 2. Create your first admin account

The system has no public admin sign-up endpoint by design, so the first
admin is created manually:

1. In Supabase, go to Authentication > Users > Add user, and create the
   admin's email and password (mark the email as confirmed).
2. In the SQL editor, insert a matching row:
   ```sql
   insert into public.admins (user_id, full_name, role)
   values ('<the-user-id-from-step-1>', 'Jane Admin', 'admin');
   ```
3. Once the first admin can sign in, additional students are added through
   the dashboard's "Add student" form or CSV import - both create the
   Supabase Auth account and the `students` row together.

## 3. Configure and run the backend

```bash
cd backend
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
# SUPABASE_JWT_SECRET, QR_HMAC_SECRET, and CODINEX_OFFICE_IPS.
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000/api/v1`, with interactive
docs at `http://localhost:8000/docs`.

### Key environment variables

| Variable | Purpose |
| --- | --- |
| `CODINEX_OFFICE_IPS` | Comma separated list of IPs allowed to check in. Set this to your office router's public IP. |
| `ENFORCE_OFFICE_WIFI` | Set to `false` only for local development/testing off the office network. |
| `QR_HMAC_SECRET` | Secret used to derive the rotating 15 second QR token. Keep this private. |
| `PRESENT_CUTOFF_TIME` / `LATE_CUTOFF_TIME` | 24-hour `HH:MM` times (in `CODINEX_TIMEZONE`) marking the present-to-late and late-to-still-late boundaries. |

## 4. Configure the frontend

The frontend is static HTML/CSS/JS with no build step. Each JS file has an
`API_BASE_URL` constant at the top - update it to point at your deployed
backend before hosting the files. `frontend/admin/js/kiosk.js` also has a
`STUDENT_SCAN_BASE_URL` constant that should match wherever
`frontend/student/scan.html` is actually hosted.

Serve `frontend/` with any static file host (Netlify, S3 + CloudFront,
Nginx, and so on). For local testing:

```bash
cd frontend
python3 -m http.server 5500
```

## 5. Day-to-day usage

- An admin opens `admin/dashboard.html`, signs in, and clicks
  "Launch kiosk view" to open `admin/kiosk.html` in a new tab, which is
  meant to be projected in the office.
- Students scan the QR code on the kiosk with their phone camera, which
  opens `student/scan.html?token=...`. If they are not signed in, they are
  sent to `student/login.html` first and returned automatically afterward.
- Each student can review their own history and attendance percentage at
  `student/dashboard.html`.

## Notes on design decisions

- **No cron/scheduler**: absent students are computed on the fly (no
  attendance row for that day) rather than written to the database
  overnight, keeping the system simpler to self-host.
- **Stateless QR token**: the token is derived from an HMAC of the current
  15 second time window rather than stored and looked up, so verification
  never requires a database round trip. `qr_sessions` rows are still
  written for audit purposes on a best-effort basis.
- **Business-day attendance percentage**: a student's percentage is
  calculated against Monday-Friday business days since their registration
  date, not calendar days.
