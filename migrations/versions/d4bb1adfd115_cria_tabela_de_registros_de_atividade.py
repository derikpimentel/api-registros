
"""cria tabela de registros de atividade

Revision ID: d4bb1adfd115
Revises:
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificadores da revisão.
revision: str = "d4bb1adfd115"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela de registros de atividade."""

    op.create_table(
        "registros_atividade",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column(
            "identificador_unico",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "repositorio",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "data_hora",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "usuario",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "data_hora_online",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove a tabela criada por esta revisão."""

    op.drop_table("registros_atividade")
