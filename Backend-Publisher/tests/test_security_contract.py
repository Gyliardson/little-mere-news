from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "202608130001_admin_rls.sql"
ADMIN_HELPER = ROOT / "frontend-web" / "src" / "lib" / "auth" / "admin.ts"
ACTIONS = ROOT / "frontend-web" / "src" / "app" / "[lang]" / "[secret_admin]" / "(dashboard)" / "news" / "actions.ts"
LAYOUT = ROOT / "frontend-web" / "src" / "app" / "[lang]" / "[secret_admin]" / "(dashboard)" / "layout.tsx"


def test_migration_enforces_public_read_and_admin_only_writes():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "alter table public.news enable row level security" in sql
    assert "for select" in sql and "to anon, authenticated" in sql
    assert "for insert" in sql and "for update" in sql and "for delete" in sql
    assert sql.count("from public.admin_users") >= 4
    assert "admin_users.user_id = auth.uid()" in sql


def test_publisher_identity_is_backed_by_database_uniqueness():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create unique index if not exists news_source_url_key" in sql
    assert "on public.news (source_url)" in sql


def test_admin_membership_cannot_be_self_managed_by_authenticated_users():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "revoke insert, update, delete on table public.admin_users from authenticated" in sql
    assert "grant select on table public.admin_users to authenticated" in sql


def test_dashboard_and_mutations_share_the_same_admin_boundary():
    helper = ADMIN_HELPER.read_text(encoding="utf-8")
    actions = ACTIONS.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")

    assert '.from("admin_users")' in helper
    assert "membership?.user_id === user.id" in helper
    assert 'import { getAdminContext } from "@/lib/auth/admin"' in actions
    assert 'import { getAdminContext } from "@/lib/auth/admin"' in layout
    assert 'accessError: "Unauthorized"' in actions
    assert 'accessError: "Forbidden"' in actions
    assert "if (!isAdmin)" in layout
