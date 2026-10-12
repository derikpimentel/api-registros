
import secrets
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import RegistroAtividade
from schemas import RegistroEntrada, RegistroResposta


app = FastAPI(
    title="API de Registros de Atividade",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)


def verificar_api_key(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
) -> None:
    if not x_api_key or not secrets.compare_digest(
        x_api_key,
        settings.api_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Credencial inválida.",
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/registros",
    response_model=RegistroResposta,
    status_code=201,
    dependencies=[Depends(verificar_api_key)],
)
def criar_registro(
    entrada: RegistroEntrada,
    db: Session = Depends(get_db),
):
    registro = RegistroAtividade(
        identificador_unico=entrada.identificador_unico,
        repositorio=entrada.repositorio,
        data_hora=entrada.data_hora,
        usuario=entrada.usuario,
        data_hora_online=datetime.now(timezone.utc),
    )

    try:
        db.add(registro)
        db.commit()
        db.refresh(registro)

        return registro

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Não foi possível salvar o registro.",
        )
