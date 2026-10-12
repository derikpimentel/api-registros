
# API de Registros de Atividade

API desenvolvida com FastAPI e PostgreSQL para receber e armazenar registros de atividade.

## Tecnologias

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Psycopg
- Pytest

## Requisitos

- Python 3.12 ou compatível
- PostgreSQL
- Git

## Instalação

Clone o repositório e entre na pasta do projeto.

Crie e ative um ambiente virtual:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Crie um arquivo `.env` a partir do modelo `.env.example` e configure as credenciais locais.

Crie os bancos PostgreSQL `registros` e `registros_teste`, conforme a configuração.

## Executar a API

```powershell
uvicorn main:app --reload
```

Documentação interativa:

http://127.0.0.1:8000/docs

Verificação de disponibilidade:

http://127.0.0.1:8000/health

## Executar os testes

```powershell
python -m pytest -v
```

Os testes utilizam o banco `registros_teste`. Não configure esse banco para apontar para dados de produção.

## Segurança

- Não publique o arquivo `.env`.
- Não compartilhe chaves de API ou senhas do banco.
- O endpoint `POST /registros` exige o cabeçalho `X-API-Key`.
- Em produção, utilize HTTPS e credenciais fortes.
- O campo `usuario` é informado pelo cliente; nesta versão, não representa uma identidade verificada por autenticação individual.
