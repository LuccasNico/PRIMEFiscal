import { useState } from 'react'
import { ROTULOS_STATUS } from '../formatos.js'
import BotaoConfirmar from './BotaoConfirmar.jsx'
import { IconeLixeira, IconeRepetir } from './Icones.jsx'

const FILTROS = [
  { id: 'todas', rotulo: 'Todas', aceita: () => true },
  { id: 'concluidas', rotulo: 'Concluídas', aceita: (nota) => nota.status === 'processada' || nota.status === 'revisada' },
  { id: 'revisar', rotulo: 'Revisar', aceita: (nota) => nota.status === 'revisar' },
  { id: 'erro', rotulo: 'Com erro', aceita: (nota) => nota.status === 'erro' },
]

/** Notas que já saíram da fila: concluídas, para revisar, corrigidas ou com erro. */
export default function ListaNotas({ notas, selecionadaId, aoSelecionar, aoRemover, aoReprocessar, aoReprocessarVarias }) {
  const [filtroId, setFiltroId] = useState('todas')

  if (!notas.length) return null

  // Se o filtro escolhido ficou sem notas (ex.: os erros foram reprocessados), volta a mostrar todas
  const escolhido = FILTROS.find((f) => f.id === filtroId)
  const filtro = notas.some(escolhido.aceita) ? escolhido : FILTROS[0]
  const visiveis = notas.filter(filtro.aceita)
  const errosReprocessaveis = notas.filter((nota) => nota.status === 'erro' && nota.tem_pdf)

  return (
    <section className="cartao" aria-labelledby="titulo-notas">
      <div className="cabecalho-lista">
        <h2 id="titulo-notas">Notas processadas ({notas.length})</h2>
        {errosReprocessaveis.length > 1 && (
          <button type="button" className="link" onClick={() => aoReprocessarVarias(errosReprocessaveis.map((n) => n.id))}>
            Reprocessar as {errosReprocessaveis.length} com erro
          </button>
        )}
      </div>

      <div className="filtros" role="group" aria-label="Filtrar por situação">
        {FILTROS.map((f) => {
          const total = notas.filter(f.aceita).length
          if (!total && f.id !== 'todas') return null
          return (
            <button
              key={f.id}
              type="button"
              className={`filtro ${f.id === filtro.id ? 'ativo' : ''}`}
              aria-pressed={f.id === filtro.id}
              onClick={() => setFiltroId(f.id)}
            >
              {f.rotulo} <span className="contagem">{total}</span>
            </button>
          )
        })}
      </div>

      <ul className="lista lista-rolavel lista-alta">
        {visiveis.map((nota) => (
          <li key={nota.id} className={`linha ${nota.id === selecionadaId ? 'selecionada' : ''}`}>
            <button type="button" className="linha-principal" onClick={() => aoSelecionar(nota.id)}>
              <span className="nome-arquivo" title={nota.arquivo}>
                {nota.arquivo}
              </span>
              <span className="secundario">{nota.dados?.tipo_documento ?? ''}</span>
              <span className={`status status-${nota.status}`}>{ROTULOS_STATUS[nota.status] ?? nota.status}</span>
            </button>
            {nota.status === 'erro' && nota.tem_pdf && (
              <button
                type="button"
                className="botao-icone"
                onClick={() => aoReprocessar(nota.id)}
                aria-label={`Reprocessar ${nota.arquivo}`}
                title="Reprocessar"
              >
                <IconeRepetir />
              </button>
            )}
            <BotaoConfirmar
              className="botao-icone"
              aoConfirmar={() => aoRemover(nota.id)}
              rotuloConfirmar="Excluir nota?"
              aria-label={`Excluir ${nota.arquivo}`}
              title="Excluir nota"
            >
              <IconeLixeira />
            </BotaoConfirmar>
          </li>
        ))}
      </ul>
    </section>
  )
}
