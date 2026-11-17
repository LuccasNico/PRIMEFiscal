// Endereço da API. Vazio no desenvolvimento (o Vite repassa /api ao backend); no deploy, o
// Static Site do Render recebe VITE_API_URL com a URL do backend (ex.: https://primefiscal-api.onrender.com)
const URL_DA_API = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

async function mensagemDeErro(resposta) {
  const corpo = await resposta.json().catch(() => null)
  const detalhe = corpo?.detail
  if (typeof detalhe === 'string') return detalhe
  // Erros de validação do FastAPI chegam como lista
  if (Array.isArray(detalhe)) return detalhe.map((item) => item.msg).join('; ')
  if (resposta.status >= 500) return 'Erro interno no servidor. Veja os detalhes no terminal do backend.'
  return `Erro ${resposta.status}`
}

async function requisitar(url, opcoes) {
  let resposta
  try {
    resposta = await fetch(URL_DA_API + url, opcoes)
  } catch {
    throw new Error('Não foi possível conectar ao servidor. Verifique se o backend está rodando.')
  }
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta))
  return resposta.status === 204 ? null : resposta.json()
}

export const obterSaude = () => requisitar('/api/saude')

export const listarNotas = () => requisitar('/api/notas')

export function enviarNotas(arquivos, abordagem) {
  const form = new FormData()
  arquivos.forEach((arquivo) => form.append('arquivos', arquivo))
  return requisitar(`/api/notas?abordagem=${abordagem}`, { method: 'POST', body: form })
}

export const removerNota = (id) => requisitar(`/api/notas/${id}`, { method: 'DELETE' })

export const esvaziarFila = () => requisitar('/api/notas?status=pendente', { method: 'DELETE' })

export const reprocessarNota = (id, abordagem) =>
  requisitar(`/api/notas/${id}/reprocessar${abordagem ? `?abordagem=${abordagem}` : ''}`, { method: 'POST' })

export const salvarNoBanco = (id) => requisitar(`/api/notas/${id}/salvar`, { method: 'POST' })

export const urlDoPdf = (id) => `${URL_DA_API}/api/notas/${id}/pdf`
