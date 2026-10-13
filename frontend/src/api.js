async function tratarResposta(resposta) {
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}))
    throw new Error(corpo.detail || `Erro ${resposta.status}`)
  }
  return resposta.json()
}

export async function enviarNota(arquivo, abordagem = 'pdf') {
  const form = new FormData()
  form.append('arquivo', arquivo)
  return tratarResposta(await fetch(`/api/notas?abordagem=${abordagem}`, { method: 'POST', body: form }))
}

export async function enviarLote(arquivos, abordagem = 'pdf') {
  const form = new FormData()
  arquivos.forEach((arquivo) => form.append('arquivos', arquivo))
  return tratarResposta(await fetch(`/api/notas/lote?abordagem=${abordagem}`, { method: 'POST', body: form }))
}

export async function obterSaude() {
  return tratarResposta(await fetch('/api/saude'))
}

export async function listarNotas() {
  return tratarResposta(await fetch('/api/notas'))
}
