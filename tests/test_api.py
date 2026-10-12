
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import settings
from database import Base, get_db, normalize_database_url
from main import app
from models import ChaveAPI, RegistroAtividade
from security import calcular_hash_chave


CHAVE_TESTE_1 = "chave-teste-sistema-a-2026"
CHAVE_TESTE_2 = "chave-teste-sistema-b-2026"
CHAVE_ADMIN_TESTE = "admin-teste-2026"

DADOS_VALIDOS = {
    "identificador_unico": "DOC-TESTE-001",
    "repositorio": "projeto-teste",
    "data_hora": "2026-10-12T02:00:00-03:00",
    "usuario": "usuario_teste",
}



@pytest.fixture
def client(monkeypatch):
    if not settings.test_database_url:
        raise RuntimeError(
            "Configure TEST_DATABASE_URL no arquivo .env."
        )

    test_engine = create_engine(
        normalize_database_url(settings.test_database_url),
        pool_pre_ping=True,
    )

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    # Configura a chave administrativa exclusivamente nos testes.
    monkeypatch.setattr(
        settings, "admin_api_key", CHAVE_ADMIN_TESTE
    )

    # Cadastra dois sistemas clientes no banco de testes.
    with TestSessionLocal() as db:
        db.add_all([
            ChaveAPI(
                nome_sistema="Sistema de Teste A",
                chave_hash=calcular_hash_chave(CHAVE_TESTE_1),
                ativa=True,
            ),
            ChaveAPI(
                nome_sistema="Sistema de Teste B",
                chave_hash=calcular_hash_chave(CHAVE_TESTE_2),
                ativa=True,
            ),
        ])
        db.commit()

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
        headers={"X-API-Key": CHAVE_TESTE_1},
        json=dados,
    )

    assert response.status_code == 422


def test_criar_registro_valido(client):
    resposta = client.post(
        "/registros",
        json=DADOS_VALIDOS,
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 201

    dados = resposta.json()

    assert dados["identificador_unico"] == DADOS_VALIDOS["identificador_unico"]
    assert dados["repositorio"] == DADOS_VALIDOS["repositorio"]
    assert dados["usuario"] == DADOS_VALIDOS["usuario"]
    assert "id" in dados
    assert "data_hora_online" in dados

    engine = create_engine(
        normalize_database_url(settings.test_database_url)
    )

    try:
        with engine.connect() as conexao:
            resultado = conexao.execute(
                text("""
                    SELECT
                        r.chave_api_id,
                        c.nome_sistema,
                        c.ultimo_uso_em
                    FROM registros_atividade AS r
                    JOIN chaves_api AS c
                        ON c.id = r.chave_api_id
                    WHERE r.id = :registro_id
                """),
                {"registro_id": dados["id"]},
            ).mappings().one()

            assert resultado["nome_sistema"] == "Sistema de Teste A"
            assert resultado["chave_api_id"] is not None
            assert resultado["ultimo_uso_em"] is not None
    finally:
        engine.dispose()


def test_segunda_chave_identifica_sistema_origem(client):
    resposta = client.post(
        "/registros",
        json=DADOS_VALIDOS,
        headers={"X-API-Key": CHAVE_TESTE_2},
    )

    assert resposta.status_code == 201

    dados = resposta.json()

    engine = create_engine(
        normalize_database_url(settings.test_database_url)
    )

    try:
        with engine.connect() as conexao:
            resultado = conexao.execute(
                text("""
                    SELECT c.nome_sistema
                    FROM registros_atividade AS r
                    JOIN chaves_api AS c
                        ON c.id = r.chave_api_id
                    WHERE r.id = :registro_id
                """),
                {"registro_id": dados["id"]},
            ).scalar_one()

            assert resultado == "Sistema de Teste B"
    finally:
        engine.dispose()


def test_administracao_sem_chave_e_bloqueada(client):
    resposta = client.post(
        "/admin/chaves",
        json={"nome_sistema": "Sistema Não Autorizado"},
    )

    assert resposta.status_code == 401


def test_admin_cria_chave_api(client):
    resposta = client.post(
        "/admin/chaves",
        json={"nome_sistema": "Sistema Novo"},
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
    )

    assert resposta.status_code == 201

    dados = resposta.json()

    assert dados["nome_sistema"] == "Sistema Novo"
    assert dados["ativa"] is True
    assert isinstance(dados["chave_api"], str)
    assert len(dados["chave_api"]) > 20

    # A chave original não deve ser armazenada em texto puro.
    engine = create_engine(
        normalize_database_url(settings.test_database_url)
    )

    try:
        with engine.connect() as conexao:
            hash_salvo = conexao.execute(
                text("""
                    SELECT chave_hash
                    FROM chaves_api
                    WHERE id = :chave_id
                """),
                {"chave_id": dados["id"]},
            ).scalar_one()

            assert hash_salvo == calcular_hash_chave(
                dados["chave_api"]
            )
            assert hash_salvo != dados["chave_api"]
    finally:
        engine.dispose()


def test_admin_lista_chaves_sem_expor_segredos(client):
    resposta = client.get(
        "/admin/chaves",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
    )

    assert resposta.status_code == 200

    dados = resposta.json()

    assert len(dados) == 2

    nomes = {chave["nome_sistema"] for chave in dados}

    assert nomes == {
        "Sistema de Teste A",
        "Sistema de Teste B",
    }

    for chave in dados:
        assert "chave_hash" not in chave
        assert "chave_api" not in chave
        assert chave["ativa"] is True


def test_admin_revoga_chave_e_bloqueia_seu_uso(client):
    # Localiza a chave do Sistema de Teste A.
    engine = create_engine(
        normalize_database_url(settings.test_database_url)
    )

    try:
        with engine.connect() as conexao:
            chave_id = conexao.execute(
                text("""
                    SELECT id
                    FROM chaves_api
                    WHERE nome_sistema = :nome
                """),
                {"nome": "Sistema de Teste A"},
            ).scalar_one()
    finally:
        engine.dispose()

    # O administrador revoga a chave.
    resposta = client.patch(
        f"/admin/chaves/{chave_id}/revogar",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
    )

    assert resposta.status_code == 200
    assert resposta.json()["ativa"] is False

    # A mesma chave não pode mais registrar atividades.
    resposta_registro = client.post(
        "/registros",
        json=DADOS_VALIDOS,
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta_registro.status_code == 401

    # A segunda chave continua funcionando.
    resposta_segunda_chave = client.post(
        "/registros",
        json=DADOS_VALIDOS,
        headers={"X-API-Key": CHAVE_TESTE_2},
    )

    assert resposta_segunda_chave.status_code == 201
