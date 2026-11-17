import { useEffect, useState } from 'react'
import * as api from './api.js'

const CHAVE_DO_MODELO = 'primefiscal.modelo'

function lerModeloGuardado() {
  try {
    return localStorage.getItem(CHAVE_DO_MODELO)
  } catch {
    return null
  }
}

/**
 * Modelos de IA que podem ser escolhidos (a lista vem da API do provedor, via backend) e o escolhido,
 * que fica guardado no navegador. `ativo` é falso quando o provedor não permite escolher ou falta a senha.
 */
export function useModelos(ativo) {
  const [catalogo, setCatalogo] = useState(null) // { padrao, modelos: [{ id, nome, descricao }] }
  const [erro, setErro] = useState(null)
  const [escolhido, setEscolhido] = useState(lerModeloGuardado)

  useEffect(() => {
    if (!ativo) return undefined
    let cancelado = false
    setErro(null)
    api
      .listarModelos()
      .then((resposta) => !cancelado && setCatalogo(resposta))
      .catch((e) => !cancelado && setErro(e.message))
    return () => {
      cancelado = true
    }
  }, [ativo])

  function escolher(id) {
    setEscolhido(id)
    try {
      localStorage.setItem(CHAVE_DO_MODELO, id)
    } catch {
      // Sem armazenamento, a escolha vale só enquanto a página estiver aberta
    }
  }

  const modelos = (ativo && catalogo?.modelos) || []
  // Um modelo guardado que saiu da lista (ex.: foi descontinuado) dá lugar ao padrão
  const modelo = modelos.some((item) => item.id === escolhido) ? escolhido : (catalogo?.padrao ?? null)

  return {
    modelos,
    // Só vai nas requisições quando a lista carregou; sem ele, o backend usa o modelo padrão
    modelo: modelos.length ? modelo : null,
    escolher,
    erro: ativo ? erro : null,
    carregando: Boolean(ativo && !catalogo && !erro),
  }
}
