# PRIMEFiscal — Planejamento do TCC

> **Título:** Aplicação de Técnicas de Inteligência Artificial no Processamento e Estruturação Automatizada de Dados de Documentos Fiscais
> **Modalidade:** Relatório Técnico (ABNT NBR 10719) — FATEC Praia Grande, CST em Análise e Desenvolvimento de Sistemas
> **Atenção:** pela Declaração de Continuidade de Orientação, o título **não pode ser alterado** na entrega final.

---

## 1. Visão geral

O usuário envia uma nota fiscal em PDF e o sistema usa IA para identificar o tipo do documento, extrair os dados e devolvê-los em um JSON padronizado e validado, pronto para:

- integração com outros sistemas (API REST documentada);
- inserção automática em banco de dados;
- integração com ERPs (via API/JSON);
- processamento de documentos em lote.

### Escopo de documentos

| Tipo | Descrição | Observação |
|---|---|---|
| **NF-e** (DANFE) | Nota fiscal eletrônica de produtos (modelo 55) | Layout nacional padronizado |
| **NFC-e** | Nota fiscal de consumidor (modelo 65), cupom | Layout nacional, formato estreito |
| **NFS-e** | Nota fiscal de serviços | Layout varia por município (o padrão nacional está em implantação). É onde a IA mais se diferencia de regras fixas |

### Campos extraídos

Número, série, chave de acesso, data de emissão, emitente (razão social, CNPJ/CPF, IE, município/UF), destinatário, itens (código, descrição, NCM, CFOP, unidade, quantidade, valor unitário, valor total), impostos (ICMS, IPI, PIS, COFINS, ISS, IBS/CBS, total aproximado de tributos) e totais (produtos, desconto, frete, total da nota).

---

## 2. Arquitetura

```
             ┌──────────────────────── Backend (FastAPI) ─────────────────────────┐
 React  ───► │ Upload ─► [Abordagem PDF]   PDF direto no Claude (multimodal)      │
 (Vite)      │        └► [Abordagem Texto] pdfplumber ─► texto ─► Claude          │
             │                              │                                     │
             │                    Saída estruturada (schema Pydantic)             │
             │                              ▼                                     │
             │              Validação fiscal (regras determinísticas)             │
             │                              ▼                                     │
             │                    JSON + status ─► Banco (SQLite/PostgreSQL)      │
             └────────────────────────────────────────────────────────────────────┘
```

### Técnicas de IA e de apoio

| Etapa | Técnica | Papel no trabalho |
|---|---|---|
| Leitura do documento | LLM multimodal (Claude) lendo o PDF nativamente: texto + imagem da página | Funciona também em notas escaneadas, sem OCR separado |
| Extração alternativa | `pdfplumber` (texto do PDF) + LLM | Comparação de custo e precisão com a leitura direta |
| Estruturação | *Structured outputs*: o modelo é obrigado a seguir o JSON Schema gerado do Pydantic | Elimina JSON malformado |
| Verificação | Regras fiscais: DV do CNPJ (inclusive o alfanumérico de 2026), DV do CPF, DV da chave de acesso (mód. 11), soma dos itens, qtd × valor unitário | Detecta "alucinações" e gera uma pontuação de confiança |
| Baseline | Expressões regulares sobre o texto extraído | Referência clássica, sem IA |

Decisão: o **Tesseract foi descartado**, porque o Claude lê PDFs escaneados diretamente. Pode voltar como trabalho futuro (modelo local sem visão).

**Provedor local (LM Studio):** além da Claude API, o backend aceita modelos locais via LM Studio (`PROVEDOR_IA=lmstudio`), usando a API compatível com OpenAI e saída restrita ao mesmo JSON Schema. Na abordagem "pdf", as páginas são convertidas em imagens (exige modelo com visão). Isso permite testar sem custo e comparar no TCC um **modelo local** (gratuito, dados não saem da máquina, LGPD) com a **nuvem** (mais preciso, pago).

### Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, SDK `anthropic`, pdfplumber, SQLAlchemy (SQLite no desenvolvimento, PostgreSQL opcional)
- **Frontend:** React + Vite
- **IA:** Claude API (Anthropic). Modelo padrão: `claude-opus-5-5`, configurável por variável de ambiente para os experimentos (ex.: `claude-sonnet-5-5`, `claude-haiku-4-5`)
- **Versionamento:** Git + GitHub (`PRIMEFiscal`)

### Endpoints (v0)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/saude` | Health check |
| POST | `/api/notas` | Envia 1 PDF e processa de forma síncrona |
| POST | `/api/notas/lote` | Envia N PDFs e processa em segundo plano |
| GET | `/api/notas` | Lista notas (filtro opcional `lote_id`) |
| GET | `/api/notas/{id}` | Detalhe (JSON completo) |
| PUT | `/api/notas/{id}` | Correção manual e revalidação |

Documentação automática em `http://localhost:8000/docs` (Swagger), usada como evidência de "integração com ERPs".

---

## 3. Avaliação experimental (diferencial do TCC)

**Gabarito automático:** toda NF-e, NFC-e e NFS-e tem um **XML oficial**. Com pares PDF + XML, o script de avaliação compara campo a campo o JSON extraído com o XML, sem rotulagem manual.

### Experimentos

| # | Comparação | Pergunta respondida |
|---|---|---|
| E1 | Baseline regex × Claude (texto) × Claude (PDF direto) | A IA supera regras fixas? Ler o PDF direto vale o custo? |
| E2 | Opus 5.5 × Sonnet 5.5 × Haiku 4.5 × modelo local (LM Studio) | Qual a relação custo × precisão de cada modelo? Um modelo local gratuito é suficiente? |
| E3 | Desempenho por tipo (NF-e × NFC-e × NFS-e) | Onde a extração é mais difícil? |
| E4 | PDF nativo × escaneado | Qual o impacto da qualidade do documento? |
| E5 | Taxa de erros detectados pela validação | As regras fiscais pegam as alucinações? |

### Métricas

- Acurácia por campo (match exato, com normalização de números, datas e CNPJ)
- Precisão, recall e F1 dos itens (casamento de linhas de produto)
- Acurácia do documento inteiro (todos os campos corretos)
- Tempo médio por nota, tokens e custo estimado por nota

### Dataset

- Meta: **50 a 100 pares PDF + XML**, distribuídos entre os 3 tipos, incluindo alguns escaneados
- Fontes: notas próprias, de familiares e colegas, ou de empresa parceira (com autorização)
- **Anonimizar** CPFs e nomes de pessoas físicas antes de versionar. Os PDFs reais **não** vão para o GitHub (`dados/` está no `.gitignore`)

---

## 4. LGPD e segurança

- Notas contêm CPF, nomes e endereços. Enviá-las à API da Anthropic é uma transferência a um operador de dados. Isso deve ser documentado no relatório.
- A chave da API fica em `.env` (nunca versionada).
- Limitar o tamanho do upload e aceitar só `application/pdf`.
- Trabalho futuro: anonimização antes do envio e modelo local.

---

## 5. Estrutura do relatório (template FATEC PG — ADS)

**Pré-textuais:** capa, folha de rosto, agradecimentos (opcional), resumo (no máximo 250 palavras), listas (ilustrações, tabelas, siglas), sumário.
*Não entram:* folha de aprovação, dedicatória, epígrafe, abstract.

| Capítulo | Conteúdo no PRIMEFiscal |
|---|---|
| **1 Introdução** | Contexto (processamento manual de notas), justificativa, público-alvo · 1.1 Objetivo geral · 1.1.1 Objetivos específicos |
| **2 Planejamento do projeto** | Fundamentação sucinta (documentos fiscais eletrônicos, IA/LLMs, extração de informação, APIs/JSON), descrição do cliente (escritórios contábeis, PMEs), recursos, aspectos técnicos |
| **3 Desenvolvimento do projeto** | 3.1 Etapas (planejamento com custos da API e viabilidade; construção com LGPD, Git, testes, avaliação contra XML, erros e acertos; implantação; manutenção) · 3.2 Critérios de inovação · 3.3 Divulgação (opcional) |
| **4 Desenvolvimento do sistema** | 4.1 Requisitos (RF/RNF) · 4.2 Processos (UML/BPMN do pipeline) · 4.3 Banco de dados (conceitual, lógico, físico) · 4.4 Projeto técnico (implementação, segurança, testes, telas, usabilidade) · *4.5 Avaliação experimental (a confirmar com o orientador)* |
| **5 Considerações finais, recomendações e limitações** | Conclusões, trabalhos futuros, limitações (NFS-e municipais, custo, LGPD) |
| **Apêndices** | Manual do usuário, schema JSON, prompts, script de avaliação |

### Formatação (Guia FATEC PG)

A4 · margens: superior/esquerda 3 cm, inferior/direita 2 cm · Arial ou Times 12 · parágrafo justificado com recuo de 1,25 cm · página no canto superior direito (tamanho 10), visível a partir da Introdução · cada capítulo em página nova · citações e referências conforme NBR 10520/6023.

### Pendências com o orientador

- [ ] Espaçamento: **simples** (template, NBR 10719 item 5.1) ou **1,5** (guia, NBR 14724)?
- [ ] Pode haver uma seção própria de avaliação experimental (4.5)?
- [ ] Integrantes do grupo (até 3) e assinatura da declaração de orientação

---

## 6. Requisitos

### Funcionais

- **RF01** Enviar um PDF de nota fiscal
- **RF02** Enviar vários PDFs (lote)
- **RF03** Identificar automaticamente o tipo (NF-e, NFC-e, NFS-e)
- **RF04** Extrair os campos da nota em JSON padronizado
- **RF05** Validar os dados extraídos e sinalizar inconsistências
- **RF06** Visualizar e corrigir manualmente os dados extraídos
- **RF07** Baixar o JSON da nota
- **RF08** Persistir as notas e consultar o histórico
- **RF09** Expor tudo via API REST documentada

### Não funcionais

- **RNF01** Tempo de processamento de até ~30 s por nota
- **RNF02** Chave de API e dados sensíveis fora do repositório
- **RNF03** Interface responsiva
- **RNF04** Modelo de IA configurável sem alterar código

---

## 7. Roadmap

- [x] **Fase 0:** Planejamento e esqueleto do projeto
- [ ] **Fase 1:** Montagem do dataset (PDF + XML) e anonimização
- [ ] **Fase 2:** Extração com Claude (PDF direto e texto) + validação fiscal (*esqueleto pronto*)
- [ ] **Fase 3:** Persistência, histórico e correção manual (*esqueleto pronto*)
- [ ] **Fase 4:** Frontend completo (upload, revisão lado a lado com o PDF, histórico)
- [ ] **Fase 5:** Processamento em lote robusto (fila, reprocessamento, status)
- [ ] **Fase 6:** Script de avaliação contra XML + baseline regex
- [ ] **Fase 7:** Experimentos E1 a E5, gráficos e tabelas
- [ ] **Fase 8:** Redação final do relatório, revisão ABNT e apresentação

A redação do relatório acontece **em paralelo**: os capítulos 1 e 2 podem começar já.
