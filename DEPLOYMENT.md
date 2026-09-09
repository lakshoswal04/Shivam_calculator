# Deployment

Frontend on **Netlify**, backend and PostgreSQL on **Render**.

```
Netlify (Next.js)  ──HTTPS──▶  Render Web Service (FastAPI)  ──▶  Render PostgreSQL
NEXT_PUBLIC_API_URL            CORS_ORIGINS, JWT_SECRET            snapshot restored once
```

Order matters: **database → backend → frontend**, because each needs the previous one's URL.

---

## 1. Database and backend on Render

Render reads [`render.yaml`](render.yaml), which declares both the Postgres instance and
the web service.

1. Render dashboard → **New → Blueprint** → select this repository.
2. Render creates `securities-db` (Postgres) and `securities-api` (web service), wires
   `DATABASE_URL` between them and generates a real `JWT_SECRET`.
3. Wait for the first deploy. It will start but have an empty database.

### Load the legal knowledge base — do not skip this

**A fresh Render deploy comes up against an empty database.** The service starts and
answers requests, but every endpoint that touches the schema fails until you load it.
Health will tell you so plainly:

```json
{ "status": "degraded", "database": "not_initialised",
  "note": "The database is reachable but the schema has not been loaded. Run: ..." }
```

Copy the **External Database URL** from the `securities-db` page in Render (the *external*
one — the internal URL is only reachable from inside Render), then run locally:

```bash
./db/snapshot/restore.sh "postgresql://…external…/legal_rules"
```

This restores the schema, 7,369 provisions, the authored rules and the demo organisation
in seconds, and verifies the result. Re-running the extraction pipeline on Render instead
would need PyMuPDF and several minutes of CPU for no benefit.

Render requires TLS for external connections; if `psql` complains, append `?sslmode=require`
to the URL.

Then confirm:

```bash
curl https://<your-service>.onrender.com/api/v1/health
# {"status":"ok","database":"ok","active_rules":13,...}
```

> **Free plan:** the service sleeps after 15 minutes idle, so the first request afterwards
> takes ~30 s. The free Postgres plan expires after 90 days.

---

## 2. Frontend on Netlify

1. Netlify → **Add new site → Import an existing project** → this repository.
2. Set **Base directory** to `frontend` — that is where Netlify looks for
   [`frontend/netlify.toml`](frontend/netlify.toml), which supplies the build command and
   Node version.

   Leave the **Publish directory** blank. Netlify builds Next.js through its OpenNext
   adapter and sets the publish directory itself; forcing it to `.next` makes Netlify
   serve the build folder as static files, and because there is no `index.html` at its
   root **every route returns "Not Found"** even though the build succeeded.
3. Add the environment variable, then deploy:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<your-service>.onrender.com/api/v1` |

   This is read at **build time** by the browser bundle, so changing it later requires a
   redeploy, not just a restart.

---

## 3. Close the CORS loop

The backend rejects browser requests from origins it does not know. On the Render service,
set:

| Key | Value |
|---|---|
| `CORS_ORIGINS` | `https://<your-site>.netlify.app` |

Comma-separate to allow more than one (for example a preview domain). Save — Render
redeploys automatically.

---

## 4. Before anyone else can reach it

**Remove the demo accounts.** The snapshot ships four accounts sharing the password
`demo1234`, and they will work on the public URL:

```bash
backend/.venv/bin/python db/seed/demo/seed_demo.py --purge --dsn "<external DATABASE_URL>"
```

That also removes the demo rule approvals, which is the point: they were approved by
`demo-reviewer`, not by a qualified legal reviewer, and nothing approved that way should
stand behind a public deployment.

**Check the environment guard is doing its job.** With `ENVIRONMENT=production` the API
refuses to start on a development `JWT_SECRET` or a localhost `DATABASE_URL`
([`backend/app/config.py`](backend/app/config.py)). If the service starts, those are set
properly.

---

## Environment variables

**Render — `securities-api`**

| Key | Source | Notes |
|---|---|---|
| `DATABASE_URL` | from `securities-db` | wired by the blueprint |
| `JWT_SECRET` | generated | never the development default |
| `ENVIRONMENT` | `production` | enables the startup guards |
| `CORS_ORIGINS` | your Netlify URL | set manually after step 2 |
| `POOL_MIN` / `POOL_MAX` | `1` / `5` | free Postgres caps connections |

**Netlify**

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<service>.onrender.com/api/v1` |

---

## Row-level security in production

Tenant isolation is enforced by PostgreSQL policies, not by application code — but **only
against a role that cannot bypass them**. Superusers and `BYPASSRLS` roles ignore policies
entirely, which is exactly how this bug hides: the policies exist, the tests pass, and every
tenant still sees every other tenant's data.

Render's database user is an ordinary role, and every tenant table is `FORCE ROW LEVEL
SECURITY`, so policies apply to it. `restore.sh` prints a warning if the connecting role
can bypass RLS. **Do not ignore that warning.**

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Frontend loads, every request fails | `CORS_ORIGINS` does not match the Netlify origin exactly (scheme and host, no trailing slash) |
| `"database": "not_initialised"` | The snapshot has not been restored. Run `db/snapshot/restore.sh` with the **external** database URL |
| `"database": "unreachable"` | `DATABASE_URL` is wrong, or you used the external URL from inside Render (use the internal one for the service) |
| `"database": "permission_denied"` | The connecting role lacks grants; re-run migration `008` against the database |
| `relation "legal.v_active_rule_versions" does not exist` | Same as `not_initialised` — the schema was never loaded |
| `active_rules: 0` with `"database": "ok"` | Rules are `PENDING` — correct until a reviewer approves them |
| First request takes 30 s | Free Render service waking from sleep |
| API will not start | The production guard rejected a dev `JWT_SECRET` or localhost `DATABASE_URL` |
| Login works, then 401 everywhere | `NEXT_PUBLIC_API_URL` points somewhere else; it is baked in at build time |
| Netlify build succeeds but every page is "Not Found" | A publish directory is set. Clear it in Site settings → Build & deploy, and remove any `publish` from `netlify.toml` |
| Netlify requests 404 against the API | `NEXT_PUBLIC_API_URL` is missing the `/api/v1` suffix |
