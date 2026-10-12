
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RegistroAtividade(Base):
    __tablename__ = "registros_atividade"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )

    identificador_unico: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    repositorio: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    usuario: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    data_hora_online: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    chave_api_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("chaves_api.id"),
        nullable=True,
    )


class ChaveAPI(Base):
    __tablename__ = "chaves_api"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )

    nome_sistema: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    chave_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    ativa: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ultimo_uso_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
