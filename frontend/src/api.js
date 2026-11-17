// Endereço da API. Vazio no desenvolvimento (o Vite repassa /api ao backend); no deploy, o
// Static Site do Render recebe VITE_API_URL com a URL do backend (ex.: https://primefiscal-api.onrender.com)
const URL_DA_API = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

// ---------- Acesso à API ----------
// Quando o backend exige senha, ela é trocada por um token com validade (POST /api/acesso), guardado
// no navegador e enviado como "Authorization: Bearer" em todas as rotas, menos /api/saude e /api/acesso.

const CHAVE_DO_ACESSO = 'primefiscal.acesso'
const ouvintesDoAcesso = new Set()

function lerAcessoGuardado() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CHAVE_DO_ACESSO))
    if (guardado?.token && new Date(guardado.expira_em) > new Date()) return guardado
  } catch {
    // Armazenamento bloqueado ou valor corrompido: a senha é pedida de novo
  }
  return null
}

let acesso = lerAcessoGuardado()

function guardarAcesso(novo) {
  acesso = novo
  try {
    if (novo) localStorage.setItem(CHAVE_DO_ACESSO, JSON.stringify(novo))
    else localStorage.removeItem(CHAVE_DO_ACESSO)
  } catch {
    // Sem armazenamento, o token vale só enquanto a página estiver aberta
  }
  ouvintesDoAcesso.forEach((ouvinte) => ouvinte(temAcesso()))
}

export const temAcesso = () => acesso != null && new Date(acesso.expira_em) > new Date()

/** Avisa quando o acesso muda (entrou, saiu ou o token venceu). Devolve a função que cancela o aviso. */
export function aoMudarAcesso(ouvinte) {
  ouvintesDoAcesso.add(ouvinte)
  return () => ouvintesDoAcesso.delete(ouvinte)
}

// ---------- Requisições ----------

async function mensagemDeErro(resposta) {
  const corpo = await resposta.json().catch(() => null)
  const detalhe = corpo?.detail
  if (typeof detalhe === 'string') return detalhe
  // Erros de validação do FastAPI chegam como lista
  if (Array.isArray(detalhe)) return detalhe.map((item) => item.msg).join('; ')
  if (resposta.status >= 500) return 'Erro interno no servidor. Veja os detalhes no terminal do backend.'
  return `Erro ${resposta.status}`
}

/** Faz a requisição e devolve a resposta. Os erros do servidor trazem o código HTTP em `status`. */
async function responder(url, opcoes = {}, { autenticada = true } = {}) {
  const comToken = autenticada && acesso != null
  const cabecalhos = { ...opcoes.headers, ...(comToken && { Authorization: `Bearer ${acesso.token}` }) }
  let resposta
  try {
    resposta = await fetch(URL_DA_API + url, { ...opcoes, headers: cabecalhos })
  } catch {
    throw new Error('Não foi possível conectar ao servidor. Verifique se o backend está rodando.')
  }
  // Token vencido ou senha trocada no servidor: a interface volta a pedir a senha
  if (resposta.status === 401 && comToken) guardarAcesso(null)
  if (!resposta.ok) {
    const erro = new Error(await mensagemDeErro(resposta))
    erro.status = resposta.status
    throw erro
  }
  return resposta
}

async function requisitar(url, opcoes, configuracao) {
  const resposta = await responder(url, opcoes, configuracao)
  return resposta.status === 204 ? null : resposta.json()
}

const SEM_TOKEN = { autenticada: false }

function comParametros(url, parametros) {
  const busca = new URLSearchParams(Object.entries(parametros).filter(([, valor]) => valor)).toString()
  return busca ? `${url}?${busca}` : url
}

export async function entrar(senha) {
  const opcoes = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ senha }) }
  guardarAcesso(await requisitar('/api/acesso', opcoes, SEM_TOKEN))
}

export const sair = () => guardarAcesso(null)

export const obterSaude = () => requisitar('/api/saude', undefined, SEM_TOKEN)

export const listarModelos = () => requisitar('/api/modelos')

export const listarNotas = () => requisitar('/api/notas')

export function enviarNotas(arquivos, abordagem, modelo) {
  const form = new FormData()
  arquivos.forEach((arquivo) => form.append('arquivos', arquivo))
  return requisitar(comParametros('/api/notas', { abordagem, modelo }), { method: 'POST', body: form })
}

export const removerNota = (id) => requisitar(`/api/notas/${id}`, { method: 'DELETE' })

export const esvaziarFila = () => requisitar('/api/notas?status=pendente', { method: 'DELETE' })

export const reprocessarNota = (id, abordagem, modelo) =>
  requisitar(comParametros(`/api/notas/${id}/reprocessar`, { abordagem, modelo }), { method: 'POST' })

export const salvarNoBanco = (id) => requisitar(`/api/notas/${id}/salvar`, { method: 'POST' })

/** O PDF original. É baixado aqui porque um <iframe> ou um link não conseguem enviar o token no cabeçalho. */
export const baixarPdf = async (id) => (await responder(`/api/notas/${id}/pdf`)).blob()
