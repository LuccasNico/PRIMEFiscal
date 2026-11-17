export const ROTULOS_STATUS = {
  pendente: 'Aguardando',
  processando: 'Processando',
  processada: 'Concluída',
  revisar: 'Revisar',
  revisada: 'Corrigida',
  erro: 'Erro',
}

export const ROTULOS_ABORDAGEM = {
  texto: 'Texto do PDF',
  pdf: 'Leitura visual do PDF',
}

export const naFila = (nota) => nota.status === 'pendente' || nota.status === 'processando'

/** Notas cuja extração terminou com sucesso podem ir para o banco de notas */
export const podeSalvarNoBanco = (nota) =>
  Boolean(nota.dados) && ['processada', 'revisar', 'revisada'].includes(nota.status)

export const moeda = (valor) =>
  valor == null ? '—' : valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

export const quantidade = (valor) =>
  valor == null ? '—' : valor.toLocaleString('pt-BR', { maximumFractionDigits: 4 })

export const tamanhoDoArquivo = (bytes) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

export function duracao(milissegundos) {
  const segundos = Math.max(0, Math.floor(milissegundos / 1000))
  return `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, '0')}`
}

/** Data e hora local, ex.: "17/11/2026, 14:32" */
export const dataHora = (iso) =>
  iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—'

/** "2026-08-11" -> "11/08/2026" */
export function dataBrasileira(iso) {
  const partes = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '')
  return partes ? `${partes[3]}/${partes[2]}/${partes[1]}` : (iso ?? '—')
}

export function cnpjOuCpf(participante) {
  const { cnpj, cpf } = participante ?? {}
  if (cnpj?.length === 14) return cnpj.replace(/^(.{2})(.{3})(.{3})(.{4})(.{2})$/, '$1.$2.$3/$4-$5')
  if (cpf?.length === 11) return cpf.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4')
  return cnpj ?? cpf ?? '—'
}

/** Chave de acesso em grupos de 4 dígitos, como aparece impressa na nota */
export const chaveDeAcesso = (chave) => (chave ? chave.replace(/(.{4})(?=.)/g, '$1 ') : '—')

export function endereco(participante) {
  const { endereco: logradouro, municipio, uf, cep } = participante ?? {}
  const cidade = [municipio, uf].filter(Boolean).join('/')
  const cepFormatado = cep?.length === 8 ? cep.replace(/^(\d{5})(\d{3})$/, '$1-$2') : cep
  return [logradouro, cidade, cepFormatado && `CEP ${cepFormatado}`].filter(Boolean).join(' · ') || '—'
}
