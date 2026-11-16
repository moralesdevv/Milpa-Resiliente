"""RLS y funciones de autorización

Revision ID: 0012
Revises: 0011
"""

from api.db.migration_support import run_statements, run_up

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_up("0012_rls")


def downgrade() -> None:
    run_statements(
        "DROP POLICY IF EXISTS report_select ON report.report",
        "DROP POLICY IF EXISTS report_insert ON report.report",
        "DROP POLICY IF EXISTS report_update ON report.report",
        "DROP POLICY IF EXISTS report_delete ON report.report",
        "ALTER TABLE report.report DISABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS sample_all ON soil.sample",
        "DROP POLICY IF EXISTS measurement_all ON soil.measurement",
        "DROP POLICY IF EXISTS declaration_all ON soil.declaration",
        "ALTER TABLE soil.sample DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE soil.measurement DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE soil.declaration DISABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS parcel_geometry_owner ON private.parcel_geometry",
        "ALTER TABLE private.parcel_geometry DISABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS farmer_select ON farm.farmer",
        "DROP POLICY IF EXISTS farmer_update ON farm.farmer",
        "DROP POLICY IF EXISTS parcel_select ON farm.parcel",
        "DROP POLICY IF EXISTS parcel_insert ON farm.parcel",
        "DROP POLICY IF EXISTS parcel_update ON farm.parcel",
        "DROP POLICY IF EXISTS parcel_delete ON farm.parcel",
        "DROP POLICY IF EXISTS parcel_history_all ON farm.parcel_history",
        "DROP POLICY IF EXISTS priority_profile_all ON farm.priority_profile",
        "DROP POLICY IF EXISTS assignment_select ON farm.technician_assignment",
        "DROP POLICY IF EXISTS assignment_owner_write ON farm.technician_assignment",
        "ALTER TABLE farm.farmer DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE farm.parcel DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE farm.parcel_history DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE farm.priority_profile DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE farm.technician_assignment DISABLE ROW LEVEL SECURITY",
        "DROP FUNCTION IF EXISTS prov.can_access_ip(uuid), farm.is_parcel_owner(uuid), farm.can_access_parcel(uuid), farm.can_access_farmer(uuid), farm.technician_assigned(uuid), farm.is_farmer_owner(uuid), auth.current_user_id()",
    )
