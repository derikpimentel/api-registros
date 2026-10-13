
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


def test_consultar_registros_exige_chave_api(client):
    resposta = client.get("/registros")

    assert resposta.status_code == 401


def test_consultar_registros_restringe_acesso_ao_proprio_sistema(client):
    # Cria um registro no Sistema A.
    resposta_a = client.post(
        "/registros",
        json={
            **DADOS_VALIDOS,
            "identificador_unico": "DOC-SISTEMA-A",
        },
        headers={"X-API-Key": CHAVE_TESTE_1},
    )
    assert resposta_a.status_code == 201

    # Cria um registro no Sistema B.
    resposta_b = client.post(
        "/registros",
        json={
            **DADOS_VALIDOS,
            "identificador_unico": "DOC-SISTEMA-B",
        },
        headers={"X-API-Key": CHAVE_TESTE_2},
    )
    assert resposta_b.status_code == 201

    # A chave A deve consultar somente os registros do Sistema A.
    resposta = client.get(
        "/registros",
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["total"] == 1
    assert len(dados["resultados"]) == 1
    assert (
        dados["resultados"][0]["identificador_unico"]
        == "DOC-SISTEMA-A"
    )


def test_chave_comum_nao_pode_consultar_outro_sistema(client):
    resposta = client.get(
        "/registros",
        params={"sistema": "Sistema de Teste B"},
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 403


def test_admin_concede_consulta_global(client):
    # Localiza a chave do Sistema A.
    resposta_lista = client.get(
        "/admin/chaves",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
    )
    assert resposta_lista.status_code == 200

    chaves = resposta_lista.json()
    chave_a = next(
        chave
        for chave in chaves
        if chave["nome_sistema"] == "Sistema de Teste A"
    )

    # Concede permissão global à chave A.
    resposta_permissao = client.patch(
        f"/admin/chaves/{chave_a['id']}/permissao-consulta-global",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
        json={"pode_consultar_todos": True},
    )

    assert resposta_permissao.status_code == 200
    assert resposta_permissao.json()["pode_consultar_todos"] is True

    # Cria um registro no Sistema B.
    resposta_registro = client.post(
        "/registros",
        json={
            **DADOS_VALIDOS,
            "identificador_unico": "DOC-GLOBAL-B",
        },
        headers={"X-API-Key": CHAVE_TESTE_2},
    )
    assert resposta_registro.status_code == 201

    # A chave A agora pode consultar especificamente o Sistema B.
    resposta_consulta = client.get(
        "/registros",
        params={"sistema": "Sistema de Teste B"},
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta_consulta.status_code == 200

    dados = resposta_consulta.json()

    assert dados["total"] == 1
    assert (
        dados["resultados"][0]["identificador_unico"]
        == "DOC-GLOBAL-B"
    )


def test_consultar_registros_aplica_filtros_e_paginacao(client):
    # Cria dois registros no Sistema A.
    for identificador in ("DOC-FILTRO-001", "DOC-FILTRO-002"):
        resposta = client.post(
            "/registros",
            json={
                **DADOS_VALIDOS,
                "identificador_unico": identificador,
            },
            headers={"X-API-Key": CHAVE_TESTE_1},
        )
        assert resposta.status_code == 201

    # Consulta usando filtros combinados e uma página de um item.
    resposta = client.get(
        "/registros",
        params={
            "repositorio": "projeto-teste",
            "usuario": "usuario_teste",
            "dia": "2026-10-12",
            "mes": "2026-10",
            "ano": 2026,
            "limite": 1,
            "deslocamento": 0,
        },
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["total"] == 2
    assert dados["limite"] == 1
    assert dados["deslocamento"] == 0
    assert len(dados["resultados"]) == 1
    assert (
        dados["resultados"][0]["identificador_unico"]
        == "DOC-FILTRO-002"
    )

    # A segunda página deve retornar o outro registro.
    resposta_segunda_pagina = client.get(
        "/registros",
        params={
            "repositorio": "projeto-teste",
            "usuario": "usuario_teste",
            "dia": "2026-10-12",
            "limite": 1,
            "deslocamento": 1,
        },
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta_segunda_pagina.status_code == 200

    dados_segunda_pagina = resposta_segunda_pagina.json()

    assert dados_segunda_pagina["total"] == 2
    assert len(dados_segunda_pagina["resultados"]) == 1
    assert (
        dados_segunda_pagina["resultados"][0]["identificador_unico"]
        == "DOC-FILTRO-001"
    )


def test_consultar_registros_rejeita_data_sem_fuso_horario(client):
    resposta = client.get(
        "/registros",
        params={"data_inicio": "2026-10-12T02:00:00"},
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 422


def test_admin_revoga_permissao_global(client):
    resposta_lista = client.get(
        "/admin/chaves",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
    )
    assert resposta_lista.status_code == 200

    chave_a = next(
        chave
        for chave in resposta_lista.json()
        if chave["nome_sistema"] == "Sistema de Teste A"
    )

    # Concede a permissão global.
    resposta = client.patch(
        f"/admin/chaves/{chave_a['id']}/permissao-consulta-global",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
        json={"pode_consultar_todos": True},
    )
    assert resposta.status_code == 200

    # Revoga a permissão global.
    resposta = client.patch(
        f"/admin/chaves/{chave_a['id']}/permissao-consulta-global",
        headers={"X-Admin-Key": CHAVE_ADMIN_TESTE},
        json={"pode_consultar_todos": False},
    )

    assert resposta.status_code == 200
    assert resposta.json()["pode_consultar_todos"] is False

    # A chave A volta a não poder consultar o Sistema B.
    resposta_consulta = client.get(
        "/registros",
        params={"sistema": "Sistema de Teste B"},
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta_consulta.status_code == 403


def test_consultar_registro_por_identificador(client):
    criacao = client.post(
        "/registros",
        json={
            **DADOS_VALIDOS,
            "identificador_unico": "DOC-BUSCA-ESPECIFICA",
        },
        headers={"X-API-Key": CHAVE_TESTE_1},
    )
    assert criacao.status_code == 201

    resposta = client.get(
        "/registros",
        params={"identificador_unico": "DOC-BUSCA-ESPECIFICA"},
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["total"] == 1
    assert (
        dados["resultados"][0]["identificador_unico"]
        == "DOC-BUSCA-ESPECIFICA"
    )


def test_consultar_registros_por_intervalo_de_data(client):
    criacao = client.post(
        "/registros",
        json={
            **DADOS_VALIDOS,
            "identificador_unico": "DOC-INTERVALO",
        },
        headers={"X-API-Key": CHAVE_TESTE_1},
    )
    assert criacao.status_code == 201

    resposta = client.get(
        "/registros",
        params={
            "data_inicio": "2026-10-12T04:59:00Z",
            "data_fim": "2026-10-12T05:01:00Z",
            "campo_data": "data_hora",
        },
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["total"] == 1
    assert (
        dados["resultados"][0]["identificador_unico"]
        == "DOC-INTERVALO"
    )


def test_consultar_registros_rejeita_limite_acima_do_maximo(client):
    resposta = client.get(
        "/registros",
        params={"limite": 101},
        headers={"X-API-Key": CHAVE_TESTE_1},
    )

    assert resposta.status_code == 422
