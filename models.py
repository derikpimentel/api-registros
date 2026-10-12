
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Identity
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
