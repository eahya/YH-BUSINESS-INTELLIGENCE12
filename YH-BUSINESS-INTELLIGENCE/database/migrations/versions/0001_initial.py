"""Initial YH BI schema, pinned to the frozen 0.1 ORM mapping snapshot."""
import importlib.util
import sys
from pathlib import Path

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

schema_path = Path(__file__).resolve().parents[1] / "schema_v1.py"
schema_spec = importlib.util.spec_from_file_location("yhbi_schema_v1", schema_path)
schema_v1 = importlib.util.module_from_spec(schema_spec)
sys.modules[schema_spec.name] = schema_v1
schema_spec.loader.exec_module(schema_v1)
metadata = schema_v1.Base.metadata


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)
