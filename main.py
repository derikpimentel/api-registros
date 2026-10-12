
import secrets
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import ChaveAPI, RegistroAtividade
from schemas import (
    ChaveAPICriar,
    ChaveAPICriada,
    ChaveAPIResposta,
    RegistroEntrada,
    RegistroResposta,
)
from security import calcular_hash_chave, gerar_chave_api


app = FastAPI(
    title="API de Registros de Atividade",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)


def verificar_admin_api_key(
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
) -> None:
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="Administração não configurada.",
        )

    if not x_admin_key or not secrets.compare_digest(
        x_admin_key,
        settings.admin_api_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Credencial administrativa inválida.",
        )


def verificar_api_key(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
    db: Session = Depends(get_db),
) -> ChaveAPI:
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Credencial inválida.",
        )

    hash_chave = calcular_hash_chave(x_api_key)

    chave = db.scalar(
        select(ChaveAPI).where(
            ChaveAPI.chave_hash == hash_chave,
            ChaveAPI.ativa.is_(True),
        )
    )

    if chave is None:
        raise HTTPException(
            status_code=401,
            detail="Credencial inválida.",
        )

    return chave


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/admin/chaves",
    response_model=ChaveAPICriada,
    status_code=201,
    dependencies=[Depends(verificar_admin_api_key)],
)
def criar_chave_cliente(
    entrada: ChaveAPICriar,
    db: Session = Depends(get_db),
):
    chave = gerar_chave_api()

    registro_chave = ChaveAPI(
        nome_sistema=entrada.nome_sistema,
        chave_hash=calcular_hash_chave(chave),
        ativa=True,
    )

    try:
        db.add(registro_chave)
        db.commit()
        db.refresh(registro_chave)

        return {
            "id": registro_chave.id,
            "nome_sistema": registro_chave.nome_sistema,
            "chave_api": chave,
            "ativa": registro_chave.ativa,
            "criada_em": registro_chave.criada_em,
        }

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Não foi possível criar a chave.",
        )


@app.get(
    "/admin/chaves",
    response_model=list[ChaveAPIResposta],
    dependencies=[Depends(verificar_admin_api_key)],
)
def listar_chaves_clientes(
    db: Session = Depends(get_db),
):
    try:
        consulta = select(ChaveAPI).order_by(ChaveAPI.id)
        return db.scalars(consulta).all()

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível listar as chaves.",
        )


@app.patch(
    "/admin/chaves/{chave_id}/revogar",
    response_model=ChaveAPIResposta,
    dependencies=[Depends(verificar_admin_api_key)],
)
def revogar_chave_cliente(
    chave_id: int,
    db: Session = Depends(get_db),
):
    try:
        chave = db.get(ChaveAPI, chave_id)

        if chave is None:
            raise HTTPException(
                status_code=404,
                detail="Chave não encontrada.",
            )

        chave.ativa = False
        db.commit()
        db.refresh(chave)

        return chave

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Não foi possível revogar a chave.",
        )


@app.post(
    "/registros",
    response_model=RegistroResposta,
    status_code=201,
)
def criar_registro(
    entrada: RegistroEntrada,
    chave_api: ChaveAPI = Depends(verificar_api_key),
    db: Session = Depends(get_db),
):
    registro = RegistroAtividade(
        identificador_unico=entrada.identificador_unico,
        repositorio=entrada.repositorio,
        data_hora=entrada.data_hora,
        usuario=entrada.usuario,
        data_hora_online=datetime.now(timezone.utc),
        chave_api_id=chave_api.id,
    )

    try:
        chave_api.ultimo_uso_em = datetime.now(timezone.utc)
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
