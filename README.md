# PRIMEFiscal

Extração e estruturação automatizada de dados de notas fiscais (NF-e, NFC-e e NFS-e) com Inteligência Artificial.

Protótipo do TCC *"Aplicação de Técnicas de Inteligência Artificial no Processamento e Estruturação Automatizada de Dados de Documentos Fiscais"* — FATEC Praia Grande, CST em Análise e Desenvolvimento de Sistemas.

O usuário envia o PDF de uma nota fiscal e o sistema usa a Claude API (Anthropic) para identificar o tipo do documento e extrair seus dados. Em seguida, os dados são validados com regras fiscais (dígitos verificadores, somas) e devolvidos em JSON, prontos para banco de dados, ERPs ou processamento em lote.

Veja o [PLANEJAMENTO.md](PLANEJAMENTO.md) para arquitetura, experimentos e roadmap.

## Estrutura

```
backend/    API FastAPI (extração com IA, validação, persistência)
frontend/   Interface React + Vite
```

## Como rodar

### Pré-requisitos

- Python 3.12+
- Node.js 20+
- Um provedor de IA, à escolha (`PROVEDOR_IA` no `.env`):
  - **Claude API:** chave em [console.anthropic.com](https://console.anthropic.com/) (uso pago por token);
  - **Google Gemini:** chave em [Google AI Studio](https://aistudio.google.com/app/apikey);
  - **API compatível com OpenAI:** OpenAI, Groq, OpenRouter, Together, Ollama, vLLM e outras que exponham `POST /v1/chat/completions`;
  - **LM Studio:** modelo local e gratuito (veja abaixo).

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # escolha o PROVEDOR_IA e preencha as variáveis dele
uvicorn app.main:app --reload
```

API em `http://localhost:8000` e documentação interativa em `http://localhost:8000/docs`.

Testes: `pytest`

### Usando um modelo local (LM Studio)

1. Instale o [LM Studio](https://lmstudio.ai/) e baixe um modelo instruído (ex.: Qwen ou Gemma, 4B a 8B parâmetros, quantização Q4). Para a abordagem `pdf`, o modelo precisa ter **visão**.
2. Na aba **Developer**, carregue o modelo e clique em **Start Server** (porta 1234). Ao carregar, ajuste o **Context Length** para **8192 ou mais**: o prompt, o texto de um DANFE e o JSON de resposta passam facilmente de 4096 tokens, e com contexto pequeno o modelo "esquece" parte da nota (impostos e itens voltam vazios).
3. No `backend/.env`, defina `PROVEDOR_IA=lmstudio` e, opcionalmente, `LMSTUDIO_MODELO` com o identificador do modelo.

Modelos locais não leem PDF diretamente: na abordagem `texto` recebem o texto extraído pelo pdfplumber; na abordagem `pdf`, as páginas são enviadas como imagens.

### Usando Google Gemini ou outra API

Para Gemini, defina no `backend/.env`:

```env
PROVEDOR_IA=gemini
GEMINI_API_KEY=sua_chave
GEMINI_MODELO=gemini-2.5-flash
```

Para provedores compatíveis com a API de Chat Completions da OpenAI, use `PROVEDOR_IA=compativel` e informe URL base (incluindo `/v1`), chave e modelo:

```env
PROVEDOR_IA=compativel
API_COMPATIVEL_URL=https://api.openai.com/v1
API_COMPATIVEL_CHAVE=sua_chave
API_COMPATIVEL_MODELO=gpt-4o-mini
API_COMPATIVEL_NOME=OpenAI
```

O formato de saída padrão é `json_schema`. Se o seu provedor não o implementar, altere `API_COMPATIVEL_FORMATO_RESPOSTA` para `json_object` ou `prompt`. Na abordagem `pdf`, Gemini e APIs compatíveis exigem um modelo com visão. APIs com protocolo próprio, que não sejam Gemini nem compatíveis com OpenAI, precisam de um adaptador específico.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Interface em `http://localhost:5173` (as chamadas a `/api` são redirecionadas para o backend).

## Privacidade

Notas fiscais contêm dados pessoais (LGPD). PDFs reais não devem ser versionados: use a pasta `dados/`, que é ignorada pelo Git.
