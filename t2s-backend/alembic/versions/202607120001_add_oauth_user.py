from alembic import op
import sqlalchemy as sa


revision = "202607120002"
down_revision = "fd19ed0b208e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uni_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False, server_default=""),
        sa.Column("email", sa.String(128), nullable=False, server_default=""),
        sa.Column("external_roles", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("uni_code", name="uq_system_user_uni_code"),
    )

    op.create_index(
        "ix_system_user_uni_code",
        "system_user",
        ["uni_code"],
    )

    op.create_table(
        "system_admin_whitelist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uni_code", sa.String(64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("remark", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "uni_code",
            name="uq_system_admin_whitelist_uni_code",
        ),
    )

    op.create_index(
        "ix_system_admin_whitelist_uni_code",
        "system_admin_whitelist",
        ["uni_code"],
    )


def downgrade():
    op.drop_table("system_admin_whitelist")
    op.drop_table("system_user")
