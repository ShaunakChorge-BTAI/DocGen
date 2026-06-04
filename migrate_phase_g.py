"""
Phase G Migration — Multi-Tenancy Foundation
============================================
Run once against an existing dbanalyser PostgreSQL database.

Usage:
    python migrate_phase_g.py
    python migrate_phase_g.py --org-name "LTFS" --admin-user admin --admin-email admin@ltfs.com --admin-password Admin@123
"""

import argparse
import re
import psycopg2
import psycopg2.extras

DB_CONN = dict(host="localhost", port=5432, database="dbanalyser",
               user="postgres", password="sa")

# Phase G DDL — executed statement-by-statement with autocommit
PHASE_G_DDL = [
    # New tables
    """CREATE TABLE IF NOT EXISTS organizations (
        id          SERIAL      PRIMARY KEY,
        name        TEXT        NOT NULL,
        slug        TEXT        NOT NULL UNIQUE,
        plan        TEXT        NOT NULL DEFAULT 'free',
        is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_orgs_slug   ON organizations(slug)",
    "CREATE INDEX IF NOT EXISTS idx_orgs_active ON organizations(is_active)",

    """CREATE TABLE IF NOT EXISTS users (
        id              SERIAL      PRIMARY KEY,
        org_id          INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        username        TEXT        NOT NULL,
        email           TEXT        NOT NULL,
        password_hash   TEXT        NOT NULL,
        role            TEXT        NOT NULL DEFAULT 'viewer',
        is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
        last_login_at   TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (org_id, username),
        UNIQUE (org_id, email)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_users_org   ON users(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",

    """CREATE TABLE IF NOT EXISTS assessment_configs (
        id              SERIAL      PRIMARY KEY,
        org_id          INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        db_registry_id  INTEGER     NOT NULL REFERENCES db_registry(id) ON DELETE CASCADE,
        config_json     JSONB       NOT NULL DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (org_id, db_registry_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_asmcfg_org ON assessment_configs(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_asmcfg_db  ON assessment_configs(db_registry_id)",

    """CREATE TABLE IF NOT EXISTS invitations (
        id          SERIAL      PRIMARY KEY,
        org_id      INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        email       TEXT        NOT NULL,
        role        TEXT        NOT NULL DEFAULT 'viewer',
        token       TEXT        NOT NULL UNIQUE,
        expires_at  TIMESTAMPTZ NOT NULL,
        accepted_at TIMESTAMPTZ,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token)",
    "CREATE INDEX IF NOT EXISTS idx_invitations_org   ON invitations(org_id)",

    # org_id on existing tables
    "ALTER TABLE db_registry     ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
    "ALTER TABLE runs            ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
    "ALTER TABLE health_trend    ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
    "ALTER TABLE audit_logs      ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
    "ALTER TABLE audit_logs      ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
    "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS db_registry_id INTEGER REFERENCES db_registry(id) ON DELETE CASCADE",
    "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS notify_email TEXT",
    "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS report_formats JSONB DEFAULT '[\"excel\",\"pdf\"]'",

    # Allow same db name across different orgs
    "ALTER TABLE db_registry DROP CONSTRAINT IF EXISTS db_registry_name_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS uidx_registry_org_name ON db_registry(org_id, name) WHERE org_id IS NOT NULL",

    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_registry_org ON db_registry(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_runs_org     ON runs(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_trend_org    ON health_trend(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_org    ON audit_logs(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_sched_org    ON scheduled_tasks(org_id)",

    # Triggers
    """CREATE OR REPLACE FUNCTION _set_updated_at()
    RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
    $$""",
    "DROP TRIGGER IF EXISTS trg_orgs_updated ON organizations",
    "CREATE TRIGGER trg_orgs_updated BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION _set_updated_at()",
    "DROP TRIGGER IF EXISTS trg_users_updated ON users",
    "CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION _set_updated_at()",
    "DROP TRIGGER IF EXISTS trg_asmcfg_updated ON assessment_configs",
    "CREATE TRIGGER trg_asmcfg_updated BEFORE UPDATE ON assessment_configs FOR EACH ROW EXECUTE FUNCTION _set_updated_at()",
]


def run(cur, sql: str, label: str = "") -> bool:
    try:
        cur.execute(sql)
        print(f"  OK   {label or (sql[:70].replace(chr(10),' ').strip())}")
        return True
    except Exception as e:
        print(f"  SKIP {label or sql[:50].strip()}: {e}")
        return False


def migrate(org_name: str, admin_user: str, admin_email: str, admin_password: str):
    conn = psycopg2.connect(**DB_CONN)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print("\n=== Phase G Migration ===\n")
    print("1. Applying DDL changes …")
    for stmt in PHASE_G_DDL:
        run(cur, stmt)

    # Create default organisation
    slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower().strip()).strip("-")
    print(f"\n2. Creating organisation {org_name!r} (slug={slug!r}) …")
    cur.execute("SELECT id FROM organizations WHERE slug=%s", (slug,))
    row = cur.fetchone()
    if row:
        org_id = row["id"]
        print(f"   Already exists  id={org_id}")
    else:
        cur.execute(
            "INSERT INTO organizations (name, slug, plan) VALUES (%s,%s,'free') RETURNING id",
            (org_name, slug))
        org_id = cur.fetchone()["id"]
        print(f"   Created  id={org_id}")

    # Assign existing data to this org
    print("\n3. Assigning existing data to org …")
    cur.execute("UPDATE db_registry SET org_id=%s WHERE org_id IS NULL", (org_id,))
    print(f"   db_registry rows updated: {cur.rowcount}")
    cur.execute("""
        UPDATE runs r SET org_id=%s
        FROM db_registry d WHERE d.id=r.db_registry_id AND r.org_id IS NULL
    """, (org_id,))
    print(f"   runs rows updated: {cur.rowcount}")
    cur.execute("UPDATE health_trend SET org_id=%s WHERE org_id IS NULL", (org_id,))
    print(f"   health_trend rows updated: {cur.rowcount}")
    cur.execute("UPDATE scheduled_tasks SET org_id=%s WHERE org_id IS NULL", (org_id,))
    print(f"   scheduled_tasks rows updated: {cur.rowcount}")

    # Create admin user
    print(f"\n4. Creating admin user {admin_user!r} …")
    cur.execute("SELECT id FROM users WHERE org_id=%s AND username=%s", (org_id, admin_user))
    if cur.fetchone():
        print("   User already exists — skipping")
    else:
        try:
            import bcrypt
            pwd_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        except ImportError:
            import hashlib
            pwd_hash = "$plain$" + hashlib.sha256(admin_password.encode()).hexdigest()
            print("   WARNING: bcrypt not installed. Run: pip install bcrypt")

        cur.execute("""
            INSERT INTO users (org_id, username, email, password_hash, role)
            VALUES (%s,%s,%s,%s,'admin') RETURNING id
        """, (org_id, admin_user, admin_email, pwd_hash))
        user_id = cur.fetchone()["id"]
        print(f"   Admin user created  id={user_id}")

    conn.close()
    print(f"""
=== Migration complete ===
  Organisation : {org_name!r}  slug={slug!r}  id={org_id}
  Admin login  : username={admin_user!r}

Next steps:
  1. Start dashboard:  python -m streamlit run dbanalyser/dashboard/app.py --server.port 8506
  2. Login via API:    POST /auth/token  {{"username":"{admin_user}","password":"<supplied>"}}
  3. Register via UI:  POST /auth/register  (new orgs self-register)
""")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--org-name",       default="LTFS")
    p.add_argument("--admin-user",     default="admin")
    p.add_argument("--admin-email",    default="admin@ltfs.com")
    p.add_argument("--admin-password", default="Admin@123")
    args = p.parse_args()
    migrate(args.org_name, args.admin_user, args.admin_email, args.admin_password)
