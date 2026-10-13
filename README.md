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
- Uma chave da [Claude API](https://console.anthropic.com/) (uso pago por token)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # e preencha ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

API em `http://localhost:8000` e documentação interativa em `http://localhost:8000/docs`.

Testes: `pytest`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Interface em `http://localhost:5173` (as chamadas a `/api` são redirecionadas para o backend).

## Privacidade

Notas fiscais contêm dados pessoais (LGPD). PDFs reais não devem ser versionados: use a pasta `dados/`, que é ignorada pelo Git.
