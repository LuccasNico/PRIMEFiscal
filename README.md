# PRIMEFiscal

Extração e estruturação automatizada de dados de notas fiscais (NF-e, NFC-e e NFS-e) com Inteligência Artificial.

Protótipo do TCC *"Aplicação de Técnicas de Inteligência Artificial no Processamento e Estruturação Automatizada de Dados de Documentos Fiscais"* — FATEC Praia Grande, CST em Análise e Desenvolvimento de Sistemas.

O usuário envia PDFs de notas fiscais, que entram em uma fila e são lidos um por vez por um modelo de IA. O modelo identifica o tipo do documento e extrai os dados. Em seguida, os dados são conferidos com regras fiscais (dígitos verificadores, somas) e ficam disponíveis em JSON, prontos para banco de dados, ERPs ou outros sistemas.

Veja o [PLANEJAMENTO.md](PLANEJAMENTO.md) para arquitetura, experimentos e roadmap.

## Estrutura

```
backend/    API FastAPI: fila de processamento, extração com IA, validação e banco de dados
frontend/   Interface React + Vite
```

## Provedores de IA

O provedor é escolhido em `PROVEDOR_IA`, no arquivo `backend/.env`. Só o bloco do provedor escolhido precisa estar preenchido.

| `PROVEDOR_IA` | Serviço | Lê o PDF direto | Observações |
|---|---|---|---|
| `gemini` (padrão) | Google Gemini | Sim | Chave gratuita no [Google AI Studio](https://aistudio.google.com/app/apikey). No plano gratuito, o Google pode usar os dados enviados: teste só com notas fictícias. |
| `claude` | Claude (Anthropic) | Sim | Chave paga em [console.anthropic.com](https://console.anthropic.com/). |
| `lmstudio` | Modelo local no [LM Studio](https://lmstudio.ai/) | Não | Gratuito e os dados não saem do computador. Veja abaixo. |
| `compativel` | Qualquer API no padrão da OpenAI: OpenAI, Groq, OpenRouter, Ollama, vLLM etc. | Não | Informe nome, URL (terminando em `/v1`), chave e modelo. |

**Abordagens de leitura**, escolhidas no envio de cada nota:

- **Texto do PDF:** o texto embutido no PDF é extraído (os quadros do DANFE viram pares "rótulo / valor") e enviado ao modelo. Mais rápido e funciona com qualquer modelo, mas não serve para notas escaneadas.
- **Leitura visual do PDF:** o modelo vê a página. Gemini e Claude recebem o próprio PDF; nos demais provedores as páginas vão como imagens, e o modelo precisa ter visão.

Para usar um serviço com protocolo próprio, crie um módulo em `backend/app/services/ia/` com as funções `extrair_de_pdf`, `extrair_de_texto` e `descrever`, e registre-o em `backend/app/services/ia/__init__.py`.

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

A API fica em `http://localhost:8000`, com documentação interativa em `http://localhost:8000/docs`. Para rodar os testes: `pytest`.

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

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/saude` | Situação da API, provedor de IA em uso e limites de envio |
| POST | `/api/notas` | Envia um ou mais PDFs para a fila (parâmetro `abordagem`: `texto` ou `pdf`) |
| GET | `/api/notas` | Lista as notas (filtros opcionais `status` e `lote_id`) |
| DELETE | `/api/notas?status=...` | Remove todas as notas com a situação informada (`pendente` esvazia a fila) |
| GET | `/api/notas/{id}` | Dados completos de uma nota |
| GET | `/api/notas/{id}/pdf` | PDF original |
| PUT | `/api/notas/{id}` | Correção manual dos dados (a nota é validada de novo) |
| POST | `/api/notas/{id}/reprocessar` | Devolve a nota à fila para uma nova extração |
| DELETE | `/api/notas/{id}` | Remove a nota (ou a retira da fila) e apaga o PDF |

## Privacidade

Notas fiscais contêm dados pessoais (LGPD). PDFs reais não devem ser versionados: use a pasta `dados/`, que é ignorada pelo Git. Os PDFs enviados ao sistema ficam em `backend/uploads/`, também ignorada.
