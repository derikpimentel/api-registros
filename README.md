# API de Registros de Atividade

API desenvolvida com **FastAPI e PostgreSQL** para receber, validar e armazenar registros de atividade enviados por sistemas clientes. A API utiliza chaves de acesso individuais, permite identificar o sistema de origem de cada registro e oferece endpoints administrativos para gerenciar essas credenciais.

## Tecnologias

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- Psycopg
- Alembic — migrações do banco de dados
- Pydantic Settings — configurações por variáveis de ambiente
- Pytest — testes automatizados

## Funcionalidades

- Recebimento e validação de registros de atividade.
- Geração automática do campo `data_hora_online` pela API.
- Identificador `id` gerado pelo banco de dados.
- Autenticação de sistemas clientes por chaves individuais.
- Armazenamento de hashes das chaves de API, em vez dos segredos originais.
- Identificação do sistema de origem de cada registro por meio da chave utilizada.
- Gerenciamento administrativo para criar, listar e revogar chaves.
- Registro da data e hora do último uso de cada chave.
- Migrações versionadas do banco com Alembic.
- Testes automatizados com banco de testes separado.
- Consulta de registros com filtros combináveis.
- Filtros por identificador, repositório, usuário, sistema e período.
- Paginação dos resultados com limite configurável.
- Restrição de consultas ao sistema associado à chave autenticada.
- Permissão administrativa para autorizar consultas entre sistemas.
- Seleção entre `data_hora` e `data_hora_online` para filtros temporais.

## Requisitos

- Python 3.12 ou compatível.
- PostgreSQL.
- Git.

## Instalação local

Clone o repositório e entre na pasta do projeto:

```powershell
git clone https://github.com/derikpimentel/api-registros.git
cd api-registros
```

Crie e ative um ambiente virtual:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

Crie um arquivo `.env` a partir do modelo `.env.example` e configure as variáveis necessárias para o ambiente local.

Configure os bancos PostgreSQL `registros` e `registros_teste`, ou utilize outros nomes, desde que as URLs correspondentes sejam configuradas corretamente.

**Nunca utilize o banco de produção como banco de testes.** A suíte de testes recria as tabelas do banco de testes.

## Configuração do ambiente

Configure no arquivo `.env` as variáveis abaixo, conforme o ambiente:

| Variável | Finalidade |
|---|---|
| `DATABASE_URL` | URL de conexão com o banco utilizado pela aplicação. |
| `TEST_DATABASE_URL` | URL exclusiva do banco utilizado pelos testes. |
| `ADMIN_API_KEY` | Segredo usado para autorizar operações administrativas. |

Exemplo ilustrativo de configuração local:

```dotenv
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@localhost:5432/registros
TEST_DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@localhost:5432/registros_teste
ADMIN_API_KEY=SUBSTITUA_POR_UM_SEGREDO_FORTE
```

Substitua os valores ilustrativos pelas configurações do seu ambiente. Não utilize literalmente esses valores como credenciais.

Gere uma chave administrativa forte com:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Guarde o resultado em local seguro e configure-o em `ADMIN_API_KEY`. Não o publique no GitHub nem o envie em mensagens.

O arquivo `.env` deve permanecer fora do controle de versão. O modelo `.env.example` deve conter apenas nomes de variáveis e valores ilustrativos, sem segredos reais.

## Banco de dados e migrações

A estrutura do banco é controlada pelo Alembic. Para aplicar as migrações pendentes ao banco configurado em `DATABASE_URL`, execute:

```powershell
python -m alembic upgrade head
```

Para consultar a revisão atual:

```powershell
python -m alembic current
```

Para verificar se os modelos e as migrações estão sincronizados:

```powershell
python -m alembic check
```

Quando houver alterações nos modelos que exijam uma nova migração, gere uma revisão com:

```powershell
python -m alembic revision --autogenerate -m "descricao_da_mudanca"
```

Revise o arquivo gerado antes de aplicá-lo. A geração automática não substitui a revisão manual da migração.

## Executar a API

Com o ambiente virtual ativado e as variáveis configuradas, aplique as migrações e inicie o servidor:

```powershell
python -m alembic upgrade head
uvicorn main:app --reload
```

A API estará disponível localmente em:

- **Documentação interativa:** http://127.0.0.1:8000/docs
- **Verificação de disponibilidade:** http://127.0.0.1:8000/health

O modo `--reload` é indicado para desenvolvimento local, não para produção.

## Autenticação

A API utiliza dois tipos de credencial, com finalidades diferentes.

### Chave de cliente — `X-API-Key`

O endpoint `POST /registros` exige uma chave de API válida e ativa no cabeçalho `X-API-Key`.

Exemplo de requisição:

```http
POST /registros
X-API-Key: SUA_CHAVE_DE_CLIENTE
Content-Type: application/json
```

Corpo ilustrativo:

```json
{
  "identificador_unico": "documento-123",
  "repositorio": "repositorio-exemplo",
  "data_hora": "2026-10-12T10:00:00-03:00",
  "usuario": "usuario-exemplo"
}
```

O campo `data_hora` deve incluir o fuso horário. O campo `data_hora_online` é gerado pela API, e o `id` é gerado pelo banco.

Cada chave está associada a um sistema cliente. A API registra essa associação para permitir identificar a origem do registro.

### Chave administrativa — `X-Admin-Key`

Os endpoints administrativos exigem o cabeçalho `X-Admin-Key`, cujo valor deve corresponder à variável `ADMIN_API_KEY`.

Essa credencial permite gerenciar chaves de clientes. Ela não deve ser utilizada como chave de cliente e não deve ser distribuída aos sistemas que enviam registros.

Se a chave administrativa não estiver configurada, as operações administrativas ficam indisponíveis.

## Endpoints disponíveis

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/health` | Verificar a disponibilidade da API. |
| `POST` | `/registros` | Validar e gravar um registro de atividade. |
| `POST` | `/admin/chaves` | Criar uma chave para um sistema cliente. |
| `GET` | `/admin/chaves` | Listar as chaves cadastradas e seus metadados. |
| `PATCH` | `/admin/chaves/{chave_id}/revogar` | Revogar uma chave existente. |
| `GET` | `/registros` | Consultar registros com filtros e paginação. |
| `PATCH` | `/admin/chaves/{chave_id}/permissao-consulta-global` | Conceder ou revogar a permissão de consulta entre sistemas. |

Os endpoints administrativos exigem `X-Admin-Key`. O endpoint de criação recebe um corpo semelhante a:

```json
{
  "nome_sistema": "Sistema de Exemplo"
}
```

Na criação, a API retorna a nova chave em texto puro **uma única vez**. O banco armazena seu hash SHA-256. Guarde a chave retornada com segurança, pois a listagem não disponibiliza o segredo original.

A listagem retorna metadados, como o nome do sistema, o estado da chave, a data de criação e o último uso. A revogação desativa a credencial, impedindo que ela autorize novas requisições.

## Consultar registros

O endpoint `GET /registros` permite consultar registros de atividade usando a chave de cliente enviada no cabeçalho `X-API-Key`.

### Parâmetros de consulta

| Parâmetro | Descrição |
|---|---|
| `identificador_unico` | Filtra pelo identificador exato do registro. |
| `repositorio` | Filtra pelo nome exato do repositório. |
| `usuario` | Filtra pelo nome informado no registro. |
| `sistema` | Filtra pelo nome do sistema de origem, conforme as permissões da chave. |
| `data_inicio` | Limite inicial do intervalo de data e hora, inclusive. |
| `data_fim` | Limite final do intervalo de data e hora, inclusive. |
| `dia` | Filtra por um dia no calendário UTC, no formato `AAAA-MM-DD`. |
| `mes` | Filtra por mês no calendário UTC, no formato `AAAA-MM`. |
| `ano` | Filtra por ano no calendário UTC. |
| `campo_data` | Escolhe `data_hora` ou `data_hora_online`. O padrão é `data_hora`. |
| `limite` | Quantidade máxima de resultados por página. Padrão: 50; máximo: 100. |
| `deslocamento` | Quantidade de resultados a ignorar antes de retornar a página. Padrão: 0. |

Os filtros podem ser combinados. Os parâmetros `data_inicio` e `data_fim` devem incluir um fuso horário. Os filtros `dia`, `mes` e `ano` utilizam os limites do calendário UTC.

### Exemplo de requisição

```http
GET /registros?usuario=usuario-exemplo&mes=2026-10&limite=50&deslocamento=0
X-API-Key: SUA_CHAVE_DE_CLIENTE
```

### Exemplo de resposta

```json
{
  "total": 1,
  "limite": 50,
  "deslocamento": 0,
  "resultados": [
    {
      "id": 1,
      "identificador_unico": "documento-123",
      "repositorio": "repositorio-exemplo",
      "data_hora": "2026-10-12T10:00:00-03:00",
      "data_hora_online": "2026-10-12T13:00:02Z",
      "usuario": "usuario-exemplo"
    }
  ]
}
```

O campo `total` representa a quantidade de registros correspondentes aos filtros antes da paginação. A lista `resultados` contém apenas os itens da página solicitada.

### Permissões de consulta

Por padrão, cada chave pode consultar os registros associados ao seu próprio sistema, inclusive aqueles registrados por outras chaves do mesmo sistema.

Uma chave com a permissão `pode_consultar_todos` habilitada pode consultar registros de outros sistemas. A permissão é administrada pelo endpoint:

```http
PATCH /admin/chaves/{chave_id}/permissao-consulta-global
X-Admin-Key: SUA_CHAVE_ADMINISTRATIVA
Content-Type: application/json
```

Para conceder a permissão:

```json
{
  "pode_consultar_todos": true
}
```

Para revogá-la:

```json
{
  "pode_consultar_todos": false
}
```

Uma chave sem permissão global que tente consultar explicitamente outro sistema recebe HTTP `403`. Registros sem chave de origem identificável não são incluídos nas consultas.

Todas as operações administrativas exigem `X-Admin-Key`. Nunca distribua essa credencial aos sistemas clientes.

## Executar os testes

Configure `TEST_DATABASE_URL` para apontar exclusivamente para o banco PostgreSQL de testes e execute:

```powershell
python -m pytest -v
```

Os testes verificam a autenticação, a gravação e a consulta de registros, os filtros, a paginação, o isolamento entre sistemas, a concessão e a revogação da permissão de consulta global e as operações administrativas.

**Atenção:** a preparação dos testes exclui e recria as tabelas do banco indicado por `TEST_DATABASE_URL`. Verifique essa URL antes de executar a suíte.

## Implantação no Render

Para implantação, configure um serviço web conectado ao repositório GitHub e um banco PostgreSQL no Render.

Configure as variáveis de ambiente do serviço:

- `DATABASE_URL`: URL de conexão com o banco de produção. Quando possível, utilize a URL interna do PostgreSQL do Render.
- `ADMIN_API_KEY`: segredo administrativo forte, gerado e armazenado com segurança.

Não configure `TEST_DATABASE_URL` para apontar para o banco de produção.

Comandos sugeridos para o serviço web:

**Build Command**

```bash
pip install -r requirements.txt
```

**Start Command**

```bash
python -m alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

O comando de inicialização aplica as migrações pendentes antes de iniciar a API. Antes de utilizar em produção, confirme que as migrações foram revisadas e que a aplicação consegue se conectar ao banco.

Após a implantação, teste `/health` e valide a autenticação e as operações administrativas. Nunca publique segredos nos logs, no repositório ou na documentação.

## Segurança

- Não publique nem compartilhe o arquivo `.env`.
- Não versione senhas, URLs de conexão com credenciais ou chaves reais.
- Utilize HTTPS em produção.
- Use segredos fortes e diferentes para administração e sistemas clientes.
- Revogue imediatamente chaves que não devam mais ser utilizadas.
- Conceda ao usuário do banco apenas as permissões necessárias.
- Faça backups regulares e proteja o acesso ao banco de produção.
- O campo `usuario` é informado pelo cliente; nesta versão, ele não representa uma identidade verificada por autenticação individual.
- A chave de cliente identifica a credencial e o sistema associado, mas não comprova, por si só, a identidade da pessoa informada no campo `usuario`.

## Estado do projeto

A suíte local conta atualmente com testes para autenticação, registro e consulta de atividades, identificação de sistemas clientes, criação e listagem de chaves de API, revogação de credenciais, filtros de consulta, paginação dos resultados, isolamento de dados entre sistemas e concessão e revogação da permissão de consulta global.

As migrações do banco de dados estão configuradas com Alembic e foram aplicadas com sucesso no ambiente local de desenvolvimento. A implantação em produção deve ser validada separadamente após a configuração do banco de dados e das variáveis de ambiente no Render.