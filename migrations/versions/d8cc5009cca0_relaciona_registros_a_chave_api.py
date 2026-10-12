
"""relaciona registros a chave API

Revision ID: d8cc5009cca0
Revises: e1107dc0f286
Create Date: 2026-10-12 08:37:53.592734
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8cc5009cca0"
down_revision: Union[str, Sequence[str], None] = "e1107dc0f286"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona o vínculo entre registros e chaves de API."""
    op.add_column(
        "registros_atividade",
        sa.Column("chave_api_id", sa.BigInteger(), nullable=True),
    )

    op.create_foreign_key(
        "fk_registros_atividade_chave_api_id_chaves_api",
        "registros_atividade",
        "chaves_api",
        ["chave_api_id"],
        ["id"],
    )


def downgrade() -> None:
    """Remove o vínculo adicionado por esta revisão."""
    op.drop_constraint(
        "fk_registros_atividade_chave_api_id_chaves_api",
        "registros_atividade",
        type_="foreignkey",
    )

    op.drop_column(
        "registros_atividade",
        "chave_api_id",
    )
