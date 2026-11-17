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
 React  ───► │ Upload ─► Fila (uma nota por vez, PDF guardado em disco)           │
 (Vite)      │   ├► [Leitura visual] PDF (ou imagens das páginas) ─► IA           │
             │   └► [Texto do PDF]   pdfplumber ─► "rótulo / valor" ─► IA         │
             │                              │                                     │
             │                    Saída estruturada (schema Pydantic)             │
             │                              ▼                                     │
             │              Validação fiscal (regras determinísticas)             │
             │                              ▼                                     │
             │                    JSON + status ─► Área de trabalho (fila)        │
             │                              ▼  usuário confere e salva            │
             │          Banco de notas: JSON + tabelas relacionais (PostgreSQL)   │
             └────────────────────────────────────────────────────────────────────┘
```

### Técnicas de IA e de apoio

| Etapa | Técnica | Papel no trabalho |
|---|---|---|
| Leitura do documento | LLM multimodal (Gemini ou Claude) lendo o PDF nativamente: texto + imagem da página | Funciona também em notas escaneadas, sem OCR separado |
| Extração alternativa | `pdfplumber` (texto do PDF) + LLM | Comparação de custo e precisão com a leitura direta |
| Estruturação | *Structured outputs*: o modelo é obrigado a seguir o JSON Schema gerado do Pydantic | Elimina JSON malformado |
| Verificação | Regras fiscais: DV do CNPJ (inclusive o alfanumérico de 2026), DV do CPF, DV da chave de acesso (mód. 11), soma dos itens, qtd × valor unitário | Detecta "alucinações" e gera uma pontuação de confiança |
| Baseline | Expressões regulares sobre o texto extraído | Referência clássica, sem IA |

Decisão: o **Tesseract foi descartado**, porque os modelos multimodais leem PDFs escaneados diretamente. Pode voltar como trabalho futuro (modelo local sem visão).

**Provedores de IA intercambiáveis:** o provedor é escolhido em `PROVEDOR_IA` no `.env`, sem mudar código. Todos recebem o mesmo prompt e a resposta é restrita ao mesmo JSON Schema:

| Provedor | Uso no TCC |
|---|---|
| **Google Gemini** (padrão) | Desenvolvimento e testes, com o plano gratuito (só notas fictícias, pois o Google pode usar os dados) |
| **Claude (Anthropic)** | Comparação com um modelo pago |
| **LM Studio** | Modelo local: gratuito e os dados não saem da máquina (LGPD), mas menos preciso |
| **API no padrão da OpenAI** | OpenAI, Groq, OpenRouter, Ollama e outros, para ampliar a comparação |

Gemini e Claude recebem o PDF direto; LM Studio e as APIs no padrão da OpenAI recebem as páginas como imagens (exigem modelo com visão).

### Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, httpx, SDK `anthropic`, pdfplumber, SQLAlchemy (SQLite no desenvolvimento, PostgreSQL no deploy)
- **Frontend:** React + Vite
- **IA:** Google Gemini por padrão (`gemini-3.5-flash`); Claude, LM Studio e APIs no padrão da OpenAI como alternativas. Provedor e modelo são configuráveis no `.env` para os experimentos
- **Versionamento:** Git + GitHub (`PRIMEFiscal`)

### Banco de dados

Script de criação (PostgreSQL): [`banco/criar_banco.sql`](banco/criar_banco.sql). As mesmas tabelas estão em `backend/app/db.py`, e um teste confere que os dois continuam iguais.

| Tabela | Conteúdo | Relacionamentos |
|---|---|---|
| `notas_fiscais` | Área de trabalho: fila e resultado de cada extração (JSON) | 1 : 0..1 com `notas_salvas` |
| `notas_salvas` | Nota conferida: identificação, totais, impostos (1:1, na própria tabela) e o JSON completo (JSONB) | N : 1 com `participantes` (emitente e destinatário) |
| `participantes` | Emitentes e destinatários, um por CNPJ/CPF (únicos) | — |
| `itens_nota` | Produtos ou serviços, numerados na ordem da nota | N : 1 com `notas_salvas` (ON DELETE CASCADE) |
| `pagamentos_nota` | Formas de pagamento | N : 1 com `notas_salvas` (ON DELETE CASCADE) |

Decisões: o JSON fica guardado inteiro (fonte fiel do que foi extraído) e as tabelas relacionais permitem consultas em SQL; a chave de acesso é única, para a mesma nota não entrar duas vezes; excluir a nota da área de trabalho não apaga a cópia salva (`processamento_id` vira NULL).

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/saude` | Situação da API, provedor de IA em uso e limites de envio |
| POST | `/api/notas` | Envia um ou mais PDFs para a fila de processamento |
| GET | `/api/notas` | Lista notas (filtros opcionais `status` e `lote_id`) |
| DELETE | `/api/notas?status=...` | Remove as notas com a situação informada (`pendente` esvazia a fila) |
| GET | `/api/notas/{id}` | Detalhe (JSON completo) |
| GET | `/api/notas/{id}/pdf` | PDF original |
| PUT | `/api/notas/{id}` | Correção manual e revalidação |
| POST | `/api/notas/{id}/reprocessar` | Devolve a nota à fila |
| POST | `/api/notas/{id}/salvar` | Salva a nota no banco de notas (ou atualiza a cópia) |
| DELETE | `/api/notas/{id}` | Remove a nota e o PDF guardado (a cópia no banco de notas continua) |
| GET | `/api/banco/notas` | Lista as notas salvas (filtros: tipo, emitente, período) |
| GET | `/api/banco/notas/{id}` | Nota salva, com o JSON extraído |
| DELETE | `/api/banco/notas/{id}` | Remove a nota do banco de notas |

Documentação automática em `http://localhost:8000/docs` (Swagger), usada como evidência de "integração com ERPs".

---

## 3. Avaliação experimental (diferencial do TCC)

**Gabarito automático:** toda NF-e, NFC-e e NFS-e tem um **XML oficial**. Com pares PDF + XML, o script de avaliação compara campo a campo o JSON extraído com o XML, sem rotulagem manual.

### Experimentos

| # | Comparação | Pergunta respondida |
|---|---|---|
| E1 | Baseline regex × IA (texto do PDF) × IA (leitura visual) | A IA supera regras fixas? Ler o PDF direto vale o custo? |
| E2 | Gemini × Claude × modelo local (LM Studio) × outras APIs | Qual a relação custo × precisão de cada modelo? Um modelo gratuito ou local é suficiente? |
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

- Notas contêm CPF, nomes e endereços. Enviá-las a uma API de IA (Google, Anthropic etc.) é uma transferência a um operador de dados. Isso deve ser documentado no relatório. No plano gratuito do Gemini, o Google pode usar os dados para melhorar seus produtos: usar só notas fictícias.
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
- [x] **Fase 2:** Extração com IA (PDF direto e texto, provedores intercambiáveis) + validação fiscal
- [ ] **Fase 3:** Persistência, histórico e correção manual (*banco de notas e script PostgreSQL prontos; faltam a tela de histórico e a edição na interface*)
- [ ] **Fase 4:** Frontend completo (upload, revisão lado a lado com o PDF, histórico)
- [x] **Fase 5:** Processamento em lote robusto (fila, reprocessamento, status)
- [ ] **Fase 6:** Script de avaliação contra XML + baseline regex
- [ ] **Fase 7:** Experimentos E1 a E5, gráficos e tabelas
- [ ] **Fase 8:** Redação final do relatório, revisão ABNT e apresentação

A redação do relatório acontece **em paralelo**: os capítulos 1 e 2 podem começar já.
