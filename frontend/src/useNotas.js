import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from './api.js'
import { naFila } from './formatos.js'

// Com notas na fila, a lista é consultada com frequência para mostrar o andamento
const INTERVALO_COM_FILA_MS = 1500
const INTERVALO_SEM_FILA_MS = 10000
const MAXIMO_POR_ENVIO_PADRAO = 50

/** A nota em processamento vem primeiro; depois, as que aguardam, na ordem em que serão processadas */
function ordemDaFila(a, b) {
  if (a.status !== b.status) return a.status === 'processando' ? -1 : 1
  return (a.enfileirado_em ?? '').localeCompare(b.enfileirado_em ?? '') || a.id - b.id
}

/**
 * Estado das notas no servidor (fila e notas concluídas) e as ações disponíveis sobre elas.
 * `autenticado`: se a pessoa já digitou a senha de acesso (só importa quando o servidor exige senha).
 */
export function useNotas(autenticado) {
  const [notas, setNotas] = useState([])
  const [saude, setSaude] = useState(undefined) // undefined = verificando; null = backend fora do ar
  const [erro, setErro] = useState(null)
  const ultimaConsulta = useRef(0)

  const verificando = saude === undefined
  // Sem a senha, nada é consultado: a API recusaria e a interface fica atrás da tela de senha
  const bloqueado = Boolean(saude?.exige_senha) && !autenticado

  /** Busca a lista de notas. Retorna true se o servidor respondeu, mesmo que com erro. */
  const atualizar = useCallback(async () => {
    // Respostas podem chegar fora de ordem; só a consulta mais recente altera a tela
    const consulta = ++ultimaConsulta.current
    try {
      const lista = await api.listarNotas()
      if (consulta === ultimaConsulta.current) setNotas(lista)
      return true
    } catch (e) {
      return e.status != null
    }
  }, [])

  const verificarSaude = useCallback(async () => {
    try {
      setSaude(await api.obterSaude())
    } catch {
      setSaude(null)
    }
  }, [])

  useEffect(() => {
    verificarSaude()
  }, [verificarSaude])

  // Ao entrar (ou quando não há senha), carrega as notas; ao sair, elas deixam a tela
  useEffect(() => {
    if (verificando) return
    if (bloqueado) {
      ultimaConsulta.current++ // descarta uma consulta que ainda esteja a caminho
      setNotas([])
    } else {
      atualizar()
    }
  }, [verificando, bloqueado, atualizar])

  const temFila = notas.some(naFila)
  useEffect(() => {
    if (bloqueado) return undefined
    const intervalo = setInterval(
      async () => {
        const respondeu = await atualizar()
        // Se o backend caiu ou voltou, atualiza o aviso do cabeçalho
        if (respondeu !== (saude != null)) verificarSaude()
      },
      temFila ? INTERVALO_COM_FILA_MS : INTERVALO_SEM_FILA_MS,
    )
    return () => clearInterval(intervalo)
  }, [temFila, saude, bloqueado, atualizar, verificarSaude])

  /** Executa uma ação no servidor, mostra o erro se houver e atualiza a lista. Retorna true se deu certo. */
  const executar = useCallback(
    async (acao) => {
      let sucesso = true
      try {
        await acao()
        setErro(null)
      } catch (e) {
        setErro(e.message)
        sucesso = false
      }
      await atualizar()
      return sucesso
    },
    [atualizar],
  )

  const maximoPorEnvio = saude?.maximo_de_arquivos_por_envio ?? MAXIMO_POR_ENVIO_PADRAO

  /**
   * Envia os arquivos para a fila. Retorna as notas criadas e quantos arquivos foram aceitos.
   * Nas ações que usam a IA, `modelo` vazio deixa o backend usar o modelo padrão.
   */
  const enviar = useCallback(
    async (arquivos, abordagem, modelo) => {
      const criadas = []
      let enviados = 0
      await executar(async () => {
        // O servidor limita a quantidade de arquivos por requisição
        for (let inicio = 0; inicio < arquivos.length; inicio += maximoPorEnvio) {
          const parte = arquivos.slice(inicio, inicio + maximoPorEnvio)
          criadas.push(...(await api.enviarNotas(parte, abordagem, modelo)))
          enviados += parte.length
        }
      })
      return { criadas, enviados }
    },
    [executar, maximoPorEnvio],
  )

  const remover = useCallback((id) => executar(() => api.removerNota(id)), [executar])
  const esvaziarFila = useCallback(() => executar(() => api.esvaziarFila()), [executar])
  const reprocessar = useCallback(
    (id, abordagem, modelo) => executar(() => api.reprocessarNota(id, abordagem, modelo)),
    [executar],
  )
  const salvarNoBanco = useCallback((id) => executar(() => api.salvarNoBanco(id)), [executar])
  const reprocessarVarias = useCallback(
    (ids, modelo) => executar(() => Promise.all(ids.map((id) => api.reprocessarNota(id, undefined, modelo)))),
    [executar],
  )

  const fila = useMemo(() => notas.filter(naFila).sort(ordemDaFila), [notas])
  const concluidas = useMemo(() => notas.filter((nota) => !naFila(nota)), [notas])

  return {
    notas,
    fila,
    concluidas,
    saude,
    bloqueado,
    erro,
    dispensarErro: () => setErro(null),
    enviar,
    remover,
    esvaziarFila,
    reprocessar,
    reprocessarVarias,
    salvarNoBanco,
  }
}
