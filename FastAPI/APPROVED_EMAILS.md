# Approved-emails allowlist

This app enforces an allowlist: **only emails (or domains) on the allowlist can
register or log in.** Anyone else gets a 403 at both `/auth/register` and
`/auth/login`.

Management is done from the server via a small CLI.

---

## One-time setup (first deploy)

1. **Restart FastAPI** once so SQLAlchemy creates the two new tables
   (`approved_emails`, `approved_domains`) via `Base.metadata.create_all()`:

   ```bash
   sudo systemctl restart fastapi
   ```

   If you prefer a manual migration instead, the SQL is:

   ```sql
   CREATE TABLE IF NOT EXISTS approved_emails (
     email     VARCHAR(255) PRIMARY KEY,
     added_by  UUID REFERENCES users(id) ON DELETE SET NULL,
     added_at  TIMESTAMPTZ DEFAULT now(),
     note      TEXT
   );
   CREATE TABLE IF NOT EXISTS approved_domains (
     domain    VARCHAR(255) PRIMARY KEY,
     added_by  UUID REFERENCES users(id) ON DELETE SET NULL,
     added_at  TIMESTAMPTZ DEFAULT now(),
     note      TEXT
   );
   ```

2. **Seed** the allowlist with everyone who already has an account, so nobody
   is locked out:

   ```bash
   cd /home/oguntoye/GravelRoad_Iowa/FastAPI
   uv run python manage_approved.py seed
   ```

After this, every pre-existing account can still sign in, and any new email
must be approved first.

---

## Day-to-day usage

All commands run from `FastAPI/`:

```bash
cd /home/oguntoye/GravelRoad_Iowa/FastAPI
```

### Approve one person

```bash
uv run python manage_approved.py add somebody@example.com
uv run python manage_approved.py add somebody@example.com --note "Iowa DOT field team"
```

### Remove one person

```bash
uv run python manage_approved.py remove somebody@example.com
```

### Approve an entire domain

Approves *everyone* at that domain (great for institutional access):

```bash
uv run python manage_approved.py add-domain iastate.edu
uv run python manage_approved.py add-domain iastate.edu --note "ISU team"
```

### Remove a domain

```bash
uv run python manage_approved.py remove-domain iastate.edu
```

### See the current allowlist

```bash
uv run python manage_approved.py list
```

Example output:

```
Approved emails (2)
  kunle@iastate.edu  [2026-04-19 12:04:11]  — seeded from existing users
  collaborator@example.com  [2026-04-19 15:22:33]  — DOT partner

Approved domains (1)
  @iastate.edu  [2026-04-19 15:25:02]  — ISU team
```

---

## What happens when a blocked email tries to sign in

Both endpoints return HTTP 403 with a generic message so a blocked user
can't probe the allowlist:

- **Register** → `403 "This email is not authorized to register for this application. Please contact the administrator."`
- **Login** → `403 "This account is not authorized. Please contact the administrator."`

---

## Notes

- Emails are stored lowercased; `Kunle@Iastate.edu` and `kunle@iastate.edu`
  are the same record.
- Domains are stored without the leading `@`; the CLI accepts both
  `iastate.edu` and `@iastate.edu` as input.
- If a user's email is on **either** the email allowlist **or** the domain
  allowlist, they pass. If you revoke their specific entry but the domain is
  still approved, they can still log in.
- No changes to passwords, JWT, or session handling — the allowlist is a
  gate applied *before* any credential check.
