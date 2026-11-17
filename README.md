# PRIMEFiscal

Extração e estruturação automatizada de dados de notas fiscais (NF-e, NFC-e e NFS-e) com Inteligência Artificial.

Protótipo do TCC *"Aplicação de Técnicas de Inteligência Artificial no Processamento e Estruturação Automatizada de Dados de Documentos Fiscais"* — FATEC Praia Grande, CST em Análise e Desenvolvimento de Sistemas.

O usuário envia PDFs de notas fiscais, que entram em uma fila e são lidos um por vez por um modelo de IA. O modelo identifica o tipo do documento e extrai os dados. Em seguida, os dados são conferidos com regras fiscais (dígitos verificadores, somas) e ficam disponíveis em JSON. Depois de conferir a nota, o usuário a salva no banco de notas, que guarda o JSON e os mesmos dados em tabelas relacionais, prontos para consultas, ERPs ou outros sistemas.

Veja o [PLANEJAMENTO.md](PLANEJAMENTO.md) para arquitetura, experimentos e roadmap.

## Estrutura

```
backend/    API FastAPI: fila de processamento, extração com IA, validação e banco de dados
frontend/   Interface React + Vite
banco/      Script SQL que cria o banco no PostgreSQL (para o deploy na nuvem)
```

## Provedores de IA

O provedor é escolhido em `PROVEDOR_IA`, no arquivo `backend/.env`. Só o bloco do provedor escolhido precisa estar preenchido.

| `PROVEDOR_IA` | Serviço | Lê o PDF direto | Observações |
|---|---|---|---|
| `gemini` (padrão) | Google Gemini | Sim | Chave gratuita no [Google AI Studio](https://aistudio.google.com/app/apikey). No plano gratuito, o Google pode usar os dados enviados: teste só com notas fictícias. |
| `claude` | Claude (Anthropic) | Sim | Chave paga em [console.anthropic.com](https://console.anthropic.com/). |
| `lmstudio` | Modelo local no [LM Studio](https://lmstudio.ai/) | Não | Gratuito e os dados não saem do computador. Veja abaixo. |
| `compativel` | Qualquer API no padrão da OpenAI: OpenAI, Groq, OpenRouter, Ollama, vLLM etc. | Não | Informe nome, URL (terminando em `/v1`), chave e modelo. |

**Escolha do modelo (Gemini):** a lista suspensa no topo da interface traz os modelos que a API do Google oferece para a chave configurada (consultada pelo backend e guardada por 10 minutos). O modelo escolhido vale para os próximos envios e reprocessamentos e fica registrado em cada nota. Sem escolha, é usado o `gemini-3.5-flash`.

**Abordagens de leitura**, escolhidas no envio de cada nota:

- **Texto do PDF:** o texto embutido no PDF é extraído (os quadros do DANFE viram pares "rótulo / valor") e enviado ao modelo. Mais rápido e funciona com qualquer modelo, mas não serve para notas escaneadas.
- **Leitura visual do PDF:** o modelo vê a página. Gemini e Claude recebem o próprio PDF; nos demais provedores as páginas vão como imagens, e o modelo precisa ter visão.

Para usar um serviço com protocolo próprio, crie um módulo em `backend/app/services/ia/` com as funções `extrair_de_pdf`, `extrair_de_texto` e `descrever`, e registre-o em `backend/app/services/ia/__init__.py`. Se o módulo também tiver `listar_modelos`, a interface passa a oferecer a escolha do modelo.

## Senha de acesso

Quando `ACESSO_SENHA` está definida, todas as rotas da API exigem um token, menos `GET /api/saude` (usada pela interface antes do login e pelo health check do Render) e `POST /api/acesso`. Assim, quem descobrir o endereço da API não lê nem apaga as notas (que têm CNPJ, CPF e endereços) nem gasta a cota de IA. A interface pede a senha uma vez, troca-a por um token em `POST /api/acesso` e o envia como `Authorization: Bearer <token>`. O token vale `ACESSO_VALIDADE_HORAS` (padrão: 12 h), é assinado com uma chave derivada da senha (trocar a senha invalida todos os tokens) e continua valendo se o servidor reiniciar. Cada senha errada demora 1 segundo para ser respondida. O PDF original é baixado pela interface com o token e exibido a partir da memória do navegador, já que um `<iframe>` não envia o cabeçalho.

Um token fixo embutido no frontend não serviria: ele fica visível no JavaScript publicado. Sem `ACESSO_SENHA` não há verificação, o que só convém no uso local; no deploy, defina sempre uma senha longa.

## Como rodar

### Pré-requisitos

- Python 3.12+
- Node.js 20+
- A chave do provedor de IA escolhido (ou o LM Studio instalado)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env
uvicorn app.main:app --reload
```

Depois, preencha no `backend/.env` a chave do provedor (para o padrão, `GEMINI_API_KEY`).

A API fica em `http://localhost:8000`, com documentação interativa em `http://localhost:8000/docs`. Para rodar os testes: `pytest` (para rodá-los num PostgreSQL, defina `DATABASE_URL_TESTES` com um banco **descartável**, que é apagado a cada teste).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

A interface fica em `http://localhost:5173` (as chamadas a `/api` são repassadas ao backend).

### Usando um modelo local (LM Studio)

1. Instale o [LM Studio](https://lmstudio.ai/) e baixe um modelo instruído (ex.: Qwen ou Gemma, de 4B a 8B parâmetros, quantização Q4). Para a leitura visual, o modelo precisa ter **visão**.
2. Carregue o modelo com **Context Length de 8192 ou mais** e ligue o servidor local (porta 1234). Com contexto menor, o prompt, o texto da nota e a resposta não cabem, e o modelo "esquece" parte da nota (impostos e itens voltam vazios).
3. No `backend/.env`, defina `PROVEDOR_IA=lmstudio` e, se quiser, `LMSTUDIO_MODELO` com o nome do modelo.

### Usando outra API no padrão da OpenAI

```env
PROVEDOR_IA=compativel
API_COMPATIVEL_NOME=Groq
API_COMPATIVEL_URL=https://api.groq.com/openai/v1
API_COMPATIVEL_CHAVE=sua_chave
API_COMPATIVEL_MODELO=nome-do-modelo
```

Se o serviço recusar o formato de resposta padrão (`json_schema`), troque `API_COMPATIVEL_FORMATO_RESPOSTA` para `json_object` ou `prompt`.

## Banco de dados

O banco tem duas partes:

- **Área de trabalho** (`notas_fiscais`): a fila e o resultado de cada extração, que ainda pode ser reprocessado ou corrigido.
- **Banco de notas** (`notas_salvas`, `participantes`, `itens_nota`, `pagamentos_nota`): as notas que o usuário conferiu e salvou com o botão **Salvar no banco**. Guarda o JSON extraído (coluna `dados`) e os mesmos dados em tabelas relacionais. Emitentes e destinatários são cadastrados uma vez por CNPJ/CPF, e a chave de acesso não se repete. Se a nota for corrigida ou reprocessada depois de salva, a interface avisa e o botão vira **Atualizar no banco**.

No desenvolvimento o banco é um SQLite em `backend/primefiscal.db`, criado automaticamente.

### Banco na nuvem (deploy)

1. Crie um banco PostgreSQL em um serviço de nuvem (Neon, Supabase, Render, Railway etc.) e copie a URL de conexão.
2. Crie as tabelas rodando [`banco/criar_banco.sql`](banco/criar_banco.sql) uma vez, no editor SQL do serviço ou pelo terminal:
   ```bash
   psql "postgresql://usuario:senha@servidor:5432/banco?sslmode=require" -f banco/criar_banco.sql
   ```
3. No servidor do backend, defina a variável `DATABASE_URL` com essa URL (`postgres://` e `postgresql://` são aceitos).

O script pode ser rodado de novo sem perder dados. Ele também liga a Row Level Security nas tabelas: em serviços que publicam as tabelas numa API REST automática (como o Supabase), essa API fica bloqueada, e só o backend acessa os dados.

## Deploy no Render

Crie os três recursos no painel do Render, na **mesma região** (assim a API e o banco se comunicam pela rede interna, sem SSL nem certificado).

1. **Banco:** New > Postgres. Depois de criado, copie a **Internal Database URL**.
2. **API:** New > Web Service, apontando para o repositório.
   - Root Directory: `backend`
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (um único processo: a fila roda numa thread dentro dele)
   - Health Check Path: `/api/saude`
   - Variáveis de ambiente:

     | Variável | Valor |
     |---|---|
     | `PYTHON_VERSION` | `3.13.5` |
     | `DATABASE_URL` | a Internal Database URL do passo 1 |
     | `GEMINI_API_KEY` | a chave do Gemini |
     | `ACESSO_SENHA` | a senha que a interface vai pedir (longa; sem ela, qualquer um vê as notas e usa a sua cota de IA) |
     | `CORS_ORIGINS` | a URL do frontend (passo 3), ex.: `https://primefiscal.onrender.com` |
     | `PASTA_UPLOADS` | `/tmp/primefiscal-uploads` |

3. **Interface:** New > Static Site, apontando para o repositório.
   - Root Directory: `frontend`
   - Build Command: `npm ci && npm run build`
   - Publish Directory: `dist`
   - Variável de ambiente: `VITE_API_URL` = a URL da API (passo 2), ex.: `https://primefiscal-api.onrender.com`. Ela é lida no build: se mudar, reimplante o site.

Como uma URL depende da outra, crie os dois serviços, copie os endereços que o Render gerou e só então preencha `CORS_ORIGINS` e `VITE_API_URL`.

O backend cria as tabelas sozinho na primeira inicialização; rodar o `banco/criar_banco.sql` é opcional.

Limites do plano gratuito: a API dorme após 15 minutos sem uso (o primeiro acesso depois disso leva cerca de 1 minuto), o banco expira 30 dias após a criação e o disco é temporário, então os PDFs originais somem quando a API dorme ou é reimplantada (os dados extraídos continuam no banco).

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/saude` | Situação da API, provedor de IA em uso, se exige senha e limites de envio |
| POST | `/api/acesso` | Troca a senha de acesso por um token |
| GET | `/api/modelos` | Modelos que podem ser escolhidos (hoje, só no Gemini) e o padrão |
| POST | `/api/notas` | Envia um ou mais PDFs para a fila (parâmetros `abordagem`: `texto` ou `pdf`; `modelo`, opcional) |
| GET | `/api/notas` | Lista as notas (filtros opcionais `status` e `lote_id`) |
| DELETE | `/api/notas?status=...` | Remove todas as notas com a situação informada (`pendente` esvazia a fila) |
| GET | `/api/notas/{id}` | Dados completos de uma nota |
| GET | `/api/notas/{id}/pdf` | PDF original |
| PUT | `/api/notas/{id}` | Correção manual dos dados (a nota é validada de novo) |
| POST | `/api/notas/{id}/reprocessar` | Devolve a nota à fila para uma nova extração (`abordagem` e `modelo` opcionais) |
| POST | `/api/notas/{id}/salvar` | Salva a nota no banco de notas (ou atualiza a cópia já salva) |
| DELETE | `/api/notas/{id}` | Remove a nota (ou a retira da fila) e apaga o PDF; a cópia no banco de notas continua |
| GET | `/api/banco/notas` | Lista as notas salvas (filtros opcionais `tipo_documento`, `documento_emitente`, `emitida_de`, `emitida_ate`) |
| GET | `/api/banco/notas/{id}` | Nota salva, com o JSON extraído |
| DELETE | `/api/banco/notas/{id}` | Remove a nota do banco de notas |

Com `ACESSO_SENHA` definida, todas as rotas, menos `/api/saude` e `/api/acesso`, exigem `Authorization: Bearer <token>` (veja [Senha de acesso](#senha-de-acesso)).

## Privacidade

Notas fiscais contêm dados pessoais (LGPD). PDFs reais não devem ser versionados: use a pasta `dados/`, que é ignorada pelo Git. Os PDFs enviados ao sistema ficam em `backend/uploads/`, também ignorada.
