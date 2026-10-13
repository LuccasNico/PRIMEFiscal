import { useCallback, useEffect, useState } from 'react'
import { enviarLote, enviarNota, listarNotas, obterSaude } from './api.js'
import AreaUpload from './components/AreaUpload.jsx'
import DetalheNota from './components/DetalheNota.jsx'
import ListaNotas from './components/ListaNotas.jsx'

export default function App() {
  const [notas, setNotas] = useState([])
  const [selecionadaId, setSelecionadaId] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [saude, setSaude] = useState(undefined)

  const atualizar = useCallback(async () => {
    try {
      setNotas(await listarNotas())
    } catch (e) {
      setErro(e.message)
    }
  }, [])

  useEffect(() => {
    atualizar()
    obterSaude()
      .then(setSaude)
      .catch(() => setSaude(null))
  }, [atualizar])

  // Enquanto houver notas de um lote em processamento, atualiza a lista periodicamente
  useEffect(() => {
    if (!notas.some((n) => n.status === 'pendente')) return
    const intervalo = setInterval(atualizar, 3000)
    return () => clearInterval(intervalo)
  }, [notas, atualizar])

  async function aoEnviar(arquivos, abordagem) {
    setEnviando(true)
    setErro(null)
    try {
      if (arquivos.length === 1) {
        const nota = await enviarNota(arquivos[0], abordagem)
        setSelecionadaId(nota.id)
      } else {
        await enviarLote(arquivos, abordagem)
      }
      await atualizar()
      return true
    } catch (e) {
      setErro(e.message)
      return false
    } finally {
      setEnviando(false)
    }
  }

  const selecionada = notas.find((n) => n.id === selecionadaId)

  return (
    <div className="app">
      <header className="cabecalho">
        <h1>PRIMEFiscal</h1>
        <p>Extração de dados de notas fiscais com Inteligência Artificial</p>
        {saude && (
          <p className="provedor">
            IA: <strong>{saude.provedor === 'lmstudio' ? 'LM Studio (local)' : 'Claude API'}</strong> · {saude.modelo}
          </p>
        )}
        {saude === null && <p className="provedor alerta-erro">Backend fora do ar (http://localhost:8000)</p>}
      </header>

      <main className="conteudo">
        <section className="coluna-esquerda">
          <AreaUpload aoEnviar={aoEnviar} enviando={enviando} />
          {erro && <p className="alerta-erro">{erro}</p>}
          <ListaNotas notas={notas} selecionadaId={selecionadaId} aoSelecionar={setSelecionadaId} />
        </section>

        <section className="coluna-direita">
          {selecionada ? (
            <DetalheNota nota={selecionada} />
          ) : (
            <p className="vazio">Envie uma nota fiscal ou selecione uma da lista.</p>
          )}
        </section>
      </main>
    </div>
  )
}
