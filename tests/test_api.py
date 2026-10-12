
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from database import Base, get_db, normalize_database_url
from main import app
from models import RegistroAtividade


DADOS_VALIDOS = {
    "identificador_unico": "DOC-TESTE-001",
    "repositorio": "projeto-teste",
    "data_hora": "2026-10-12T02:00:00-03:00",
    "usuario": "usuario_teste",
}


@pytest.fixture
def client():
    if not settings.test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL não está configurada."
        )

    test_engine = create_engine(
        normalize_database_url(settings.test_database_url),
        pool_pre_ping=True,
    )

    # Este banco é exclusivo para testes.
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_registro_sem_chave_api(client):
    response = client.post(
        "/registros",
        json=DADOS_VALIDOS,
    )

    assert response.status_code == 401


def test_registro_com_chave_incorreta(client):
    response = client.post(
        "/registros",
        headers={"X-API-Key": "chave-incorreta"},
        json=DADOS_VALIDOS,
    )

    assert response.status_code == 401


def test_registro_com_campo_extra(client):
    dados = {**DADOS_VALIDOS, "id": 9999}

    response = client.post(
        "/registros",
        headers={"X-API-Key": settings.api_key},
        json=dados,
    )

    assert response.status_code == 422


def test_criar_registro_valido(client):
    inicio = datetime.now(timezone.utc)

    response = client.post(
        "/registros",
        headers={"X-API-Key": settings.api_key},
        json=DADOS_VALIDOS,
    )

    fim = datetime.now(timezone.utc)

    assert response.status_code == 201

    dados = response.json()

    # O banco deve gerar o ID.
    assert isinstance(dados["id"], int)
    assert dados["id"] > 0

    # Os dados enviados pelo cliente devem ser preservados.
    assert dados["identificador_unico"] == "DOC-TESTE-001"
    assert dados["repositorio"] == "projeto-teste"
    assert dados["usuario"] == "usuario_teste"

    # A API deve gerar seu próprio horário de recebimento.
    horario_online = datetime.fromisoformat(
        dados["data_hora_online"]
    )

    assert horario_online.tzinfo is not None
    assert inicio <= horario_online <= fim

    # Confirma que o registro realmente está no banco de testes.
    with create_engine(
        normalize_database_url(settings.test_database_url)
    ).connect() as conexao:
        registro = conexao.execute(
            RegistroAtividade.__table__.select().where(
                RegistroAtividade.id == dados["id"]
            )
        ).mappings().one_or_none()

        assert registro is not None
        assert registro["identificador_unico"] == "DOC-TESTE-001"
