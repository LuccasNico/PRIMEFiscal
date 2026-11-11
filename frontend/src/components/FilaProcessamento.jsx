import { useEffect, useState } from 'react'
import { duracao, ROTULOS_ABORDAGEM } from '../formatos.js'
import BotaoConfirmar from './BotaoConfirmar.jsx'
import { Girando, IconeFechar } from './Icones.jsx'

/** Hora atual, atualizada a cada segundo enquanto `ativo` for verdadeiro (para o cronômetro) */
function useRelogio(ativo) {
  const [agora, setAgora] = useState(Date.now())
  useEffect(() => {
    if (!ativo) return
    setAgora(Date.now())
    const intervalo = setInterval(() => setAgora(Date.now()), 1000)
    return () => clearInterval(intervalo)
  }, [ativo])
  return agora
}

/** Notas enviadas que ainda não foram processadas: a que está com a IA e as que aguardam a vez. */
export default function FilaProcessamento({ fila, selecionadaId, aoSelecionar, aoRemover, aoEsvaziar }) {
  const emProcessamento = fila.find((nota) => nota.status === 'processando')
  const aguardando = fila.filter((nota) => nota.status === 'pendente')
  const agora = useRelogio(Boolean(emProcessamento))

  if (!fila.length) return null

  return (
    <section className="cartao" aria-labelledby="titulo-fila">
      <div className="cabecalho-lista">
        <h2 id="titulo-fila">Fila de processamento ({fila.length})</h2>
        {aguardando.length > 0 && (
          <BotaoConfirmar className="link" aoConfirmar={aoEsvaziar} rotuloConfirmar="Remover todas?">
            Esvaziar fila
          </BotaoConfirmar>
        )}
      </div>

      <ul className="lista lista-rolavel">
        {fila.map((nota) => {
          const processando = nota.status === 'processando'
          return (
            <li key={nota.id} className={`linha ${nota.id === selecionadaId ? 'selecionada' : ''}`}>
              <button type="button" className="linha-principal" onClick={() => aoSelecionar(nota.id)}>
                <span className="marcador">
                  {processando ? <Girando /> : <span className="posicao">{aguardando.indexOf(nota) + 1}º</span>}
                </span>
                <span className="nome-arquivo" title={nota.arquivo}>
                  {nota.arquivo}
                </span>
                <span className="secundario" title={ROTULOS_ABORDAGEM[nota.abordagem]}>
                  {processando
                    ? `Processando · ${duracao(agora - new Date(nota.iniciado_em).getTime())}`
                    : 'Aguardando'}
                </span>
              </button>
              <button
                type="button"
                className="botao-icone"
                onClick={() => aoRemover(nota.id)}
                disabled={processando}
                aria-label={`Remover ${nota.arquivo} da fila`}
                title={processando ? 'Em processamento: aguarde a conclusão para remover' : 'Remover da fila'}
              >
                <IconeFechar />
              </button>
            </li>
          )
        })}
      </ul>

      <p className="dica">As notas são processadas uma por vez, na ordem de envio.</p>
    </section>
  )
}
