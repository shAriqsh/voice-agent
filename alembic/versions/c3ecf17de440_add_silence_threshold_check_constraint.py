"""add silence threshold check constraint

Revision ID: c3ecf17de440
Revises: ca6d75ae7511
Create Date: 2026-11-27 09:12:17.667418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3ecf17de440'
down_revision: Union[str, Sequence[str], None] = 'ca6d75ae7511'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_agent_profile_silence_thresholds",
        "agent_profiles",
        "silence_hangup_ms > silence_reprompt_ms",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_agent_profile_silence_thresholds",
        "agent_profiles",
        type_="check",
    )
