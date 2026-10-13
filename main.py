
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import ChaveAPI, RegistroAtividade
from schemas import (
    ChaveAPICriar,
    ChaveAPICriada,
    ChaveAPIResposta,
    PermissaoConsultaGlobal,
    RegistroEntrada,
    RegistroResposta,
    RegistroPaginadoResposta,
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
            "pode_consultar_todos": registro_chave.pode_consultar_todos,
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


@app.patch(
    "/admin/chaves/{chave_id}/permissao-consulta-global",
    response_model=ChaveAPIResposta,
    dependencies=[Depends(verificar_admin_api_key)],
)
def alterar_permissao_consulta_global(
    chave_id: int,
    entrada: PermissaoConsultaGlobal,
    db: Session = Depends(get_db),
):
    try:
        chave = db.get(ChaveAPI, chave_id)

        if chave is None:
            raise HTTPException(
                status_code=404,
                detail="Chave não encontrada.",
            )

        chave.pode_consultar_todos = entrada.pode_consultar_todos

        db.commit()
        db.refresh(chave)

        return chave

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Não foi possível alterar a permissão.",
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


@app.get(
    "/registros",
    response_model=RegistroPaginadoResposta,
)
def consultar_registros(
    identificador_unico: str | None = Query(default=None),
    repositorio: str | None = Query(default=None),
    usuario: str | None = Query(default=None),
    sistema: str | None = Query(default=None),
    data_inicio: datetime | None = Query(default=None),
    data_fim: datetime | None = Query(default=None),
    dia: date | None = Query(default=None),
    mes: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    ano: int | None = Query(default=None, ge=1, le=9998),
    campo_data: Literal["data_hora", "data_hora_online"] = "data_hora",
    limite: int = Query(default=50, ge=1, le=100),
    deslocamento: int = Query(default=0, ge=0),
    chave_api: ChaveAPI = Depends(verificar_api_key),
    db: Session = Depends(get_db),
):
    # 1. Validar os filtros de data.
    if data_inicio is not None and data_inicio.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="data_inicio deve incluir fuso horário.",
        )

    if data_fim is not None and data_fim.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="data_fim deve incluir fuso horário.",
        )

    if (
        data_inicio is not None
        and data_fim is not None
        and data_inicio > data_fim
    ):
        raise HTTPException(
            status_code=422,
            detail="data_inicio não pode ser posterior a data_fim.",
        )

    # 2. Impedir que uma chave comum consulte outro sistema.
    if (
        not chave_api.pode_consultar_todos
        and sistema is not None
        and sistema != chave_api.nome_sistema
    ):
        raise HTTPException(
            status_code=403,
            detail="Sua chave não tem permissão para consultar este sistema.",
        )

    # 3. Construir a consulta base.
    # O JOIN garante que só sejam considerados registros
    # cuja chave de origem existe na tabela chaves_api.
    consulta = (
        select(RegistroAtividade)
        .join(
            ChaveAPI,
            RegistroAtividade.chave_api_id == ChaveAPI.id,
        )
    )

    filtros = []

    # 4. Aplicar o escopo de acesso da chave autenticada.
    if chave_api.pode_consultar_todos:
        if sistema is not None:
            filtros.append(ChaveAPI.nome_sistema == sistema)
    else:
        filtros.append(
            ChaveAPI.nome_sistema == chave_api.nome_sistema
        )

    # 5. Aplicar os filtros textuais.
    if identificador_unico is not None:
        filtros.append(
            RegistroAtividade.identificador_unico == identificador_unico
        )

    if repositorio is not None:
        filtros.append(
            RegistroAtividade.repositorio == repositorio
        )

    if usuario is not None:
        filtros.append(
            RegistroAtividade.usuario == usuario
        )

    # 6. Selecionar a coluna de data que será consultada.
    coluna_data = getattr(RegistroAtividade, campo_data)

    # 7. Aplicar o intervalo explícito.
    if data_inicio is not None:
        filtros.append(
            coluna_data >= data_inicio.astimezone(timezone.utc)
        )

    if data_fim is not None:
        filtros.append(
            coluna_data <= data_fim.astimezone(timezone.utc)
        )

    # 8. Aplicar o filtro por dia UTC.
    if dia is not None:
        inicio_dia = datetime(
            dia.year, dia.month, dia.day, tzinfo=timezone.utc
        )
        fim_dia = inicio_dia + timedelta(days=1)

        filtros.append(coluna_data >= inicio_dia)
        filtros.append(coluna_data < fim_dia)

    # 9. Aplicar o filtro por mês UTC, no formato AAAA-MM.
    if mes is not None:
        ano_mes, mes_numero = map(int, mes.split("-"))

        inicio_mes = datetime(
            ano_mes, mes_numero, 1, tzinfo=timezone.utc
        )

        if mes_numero == 12:
            inicio_proximo_mes = datetime(
                ano_mes + 1, 1, 1, tzinfo=timezone.utc
            )
        else:
            inicio_proximo_mes = datetime(
                ano_mes, mes_numero + 1, 1, tzinfo=timezone.utc
            )

        filtros.append(coluna_data >= inicio_mes)
        filtros.append(coluna_data < inicio_proximo_mes)

    # 10. Aplicar o filtro por ano UTC.
    if ano is not None:
        inicio_ano = datetime(ano, 1, 1, tzinfo=timezone.utc)
        inicio_proximo_ano = datetime(
            ano + 1, 1, 1, tzinfo=timezone.utc
        )

        filtros.append(coluna_data >= inicio_ano)
        filtros.append(coluna_data < inicio_proximo_ano)

    # 11. Contar todos os resultados antes da paginação.
    consulta_total = (
        select(func.count(RegistroAtividade.id))
        .select_from(RegistroAtividade)
        .join(
            ChaveAPI,
            RegistroAtividade.chave_api_id == ChaveAPI.id,
        )
        .where(*filtros)
    )

    # 12. Ordenar e paginar no próprio banco de dados.
    consulta_resultados = (
        consulta
        .where(*filtros)
        .order_by(
            coluna_data.desc(),
            RegistroAtividade.id.desc(),
        )
        .limit(limite)
        .offset(deslocamento)
    )

    try:
        total = db.scalar(consulta_total) or 0
        resultados = db.scalars(consulta_resultados).all()

        return {
            "total": total,
            "limite": limite,
            "deslocamento": deslocamento,
            "resultados": resultados,
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível consultar os registros.",
        )
