# Microgenesys Agentic-AI

API de chat de IA construída com FastAPI, organizada em camadas (routers, services, schemas, config) e pronta para uso em produção com autenticação por Bearer Token, logs estruturados, request-id, access logs, healthcheck público, execução não bloqueante e pipeline de CI.

## Principais funcionalidades

- Endpoints HTTP:
  - POST /chat → processa a mensagem e retorna o texto gerado (não bloqueia o event loop).
  - POST /agent → enfileira o processamento em background e retorna um ACK imediato.
  - GET /health → healthcheck público (sem autenticação).
- Sessões com estado: histórico persistido em S3 por chat_id (via S3SessionManager).
- Autenticação: Bearer Token aplicado globalmente (exceto /health).
- Observabilidade: logs estruturados, X-Request-ID por requisição e access logs.
- Confiabilidade/Performance: retries com backoff exponencial + timeout e offload de blocantes para ThreadPoolExecutor.

## Estrutura do projeto

```bash
├── agents/
│   ├── __init__.py
│   └── agent.py
├── api/
│   ├── __init__.py
│   └── routes.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── schemas/
│   ├── __init__.py
│   ├── requests.py
│   └── responses.py
├── services/
│   └── agent_service.py
├── utils/
│   ├── access_log.py
│   ├── auth.py
│   └── request_id.py
├── tools/
│   ├── __init__.py
│   └── gerador_senhas.py
├── tests/
│   └── test_health_and_request_id.py
├── .github/workflows/ci.yml
├── main.py
├── requirements.txt
├── README.md
└── .env (local)
```

## Pré‑requisitos

- Python 3.12+
- Conta AWS com acesso ao Amazon Bedrock e Amazon S3 (se for usar sessões persistentes).
- Credenciais AWS configuradas (ex.: `~/.aws/credentials` ou variáveis de ambiente) quando aplicável.

## Instalação

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração (Pydantic Settings)

Crie um arquivo `.env` na raiz para desenvolvimento local (em produção, injete as variáveis no ambiente):

```ini
# Autenticação
API_TOKEN="seu-token-seguro-aqui"

# Modelo
MODEL_ID="modelo-da-bedrock"

# Sessões (opcional, mas recomendado para histórico)
S3_BUCKET_SESSIONS="seu-bucket"

# AWS (opcionais)
AWS_PROFILE="seu-profile"
AWS_REGION="us-east-1"

# CORS (CSV) – deixe vazio para desabilitar
CORS_ALLOW_ORIGINS="https://seu-dominio.com,https://outro.com"

# Logs
LOG_LEVEL="INFO"  # DEBUG/INFO/WARNING/ERROR

# Confiabilidade/Performance
AGENT_MAX_RETRIES=2
AGENT_RETRY_BACKOFF_BASE_SEC=0.5
AGENT_RETRY_BACKOFF_MAX_SEC=5
AGENT_CALL_TIMEOUT_SEC=45
```

Os campos são carregados por `config/settings.py`. Variáveis não definidas permanecem com padrão seguro quando possível. Se `MODEL_ID` estiver ausente, o app inicia mas loga erro no startup.

## Execução

- Desenvolvimento (auto‑reload):
  ```sh
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
- Produção (exemplo):
  ```sh
  gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 main:app \
    --timeout 60 --graceful-timeout 30 --keep-alive 5
  ```

## Autenticação (Bearer Token)

- Todas as rotas exigem `Authorization: Bearer <token>`, exceto `/health`.
- Se `API_TOKEN` não estiver configurado, a API retorna 500 (falha fechada para evitar execução insegura).
- Implementação modular em `utils/auth.py` (pode ser reutilizada em outros projetos). Consulte também `docs/fast-api-auth-token.md`.

Exemplo de uso (curl):

```sh
export API_TOKEN=seu-token
curl -s -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/health
```

## Endpoints e exemplos

- GET /health (público):
  ```sh
  curl -s http://localhost:8000/health
  ```
  Resposta: `{ "status": "ok" }`

- POST /chat (retorna texto):
  ```sh
  curl -s -X POST "http://localhost:8000/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -d '{
          "input": "Olá, gere uma senha de 15 caracteres",
          "chat_id": "sessao-123"
        }'
  ```
  Resposta (ex.): `{ "text": "sua-resposta-aqui" }`

- POST /agent (processamento em background, retorno imediato):
  ```sh
  curl -s -X POST "http://localhost:8000/agent" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -d '{
          "input": "Olá, gere uma senha de 15 caracteres",
          "chat_id": "sessao-123"
        }'
  ```
  Resposta: `{ "status": "received", "message": "Request received. Processing will be done in the background." }`

## Observabilidade

- Logs estruturados com nível configurável por `LOG_LEVEL`.
- Middleware de Request‑ID (`utils/request_id.py`): adiciona/propaga `x-request-id` nas respostas.
- Access logs (`utils/access_log.py`): um log por requisição com método, caminho, status, duração e IP.

## Testes e CI

- Testes locais:
  ```sh
  pytest -q
  ```
  O workflow de CI (`.github/workflows/ci.yml`) já injeta valores dummy para `API_TOKEN` e `MODEL_ID`.

- Pre‑commit (opcional):
  ```sh
  pip install pre-commit && pre-commit install
  ```

- CI (GitHub Actions): lint (ruff), verificação de formatação (black), isort, testes (pytest) e auditoria de segurança (pip-audit). Algumas etapas estão como não‑bloqueantes inicialmente.

## Dicas e troubleshooting

- Erros de credenciais AWS: verifique `AWS_PROFILE`/`AWS_REGION` e suas credenciais locais.
- `S3_BUCKET_SESSIONS` é opcional, mas necessário para persistir histórico em S3; sem ele, a inicialização do agente poderá falhar ao tentar salvar estado.
- CORS: defina `CORS_ALLOW_ORIGINS` (CSV). Se vazio, CORS fica desabilitado.
- Timeout/Retentativas: ajuste `AGENT_*` conforme sua necessidade e latência esperada do provedor LLM.
