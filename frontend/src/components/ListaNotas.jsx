const ROTULOS_STATUS = {
  pendente: 'Processando',
  processada: 'OK',
  revisar: 'Revisar',
  revisada: 'Revisada',
  erro: 'Erro',
}

export default function ListaNotas({ notas, selecionadaId, aoSelecionar }) {
  if (!notas.length) return null

  return (
    <div className="cartao">
      <h2>Notas processadas</h2>
      <ul className="lista-notas">
        {notas.map((nota) => (
          <li
            key={nota.id}
            className={nota.id === selecionadaId ? 'selecionada' : ''}
            onClick={() => aoSelecionar(nota.id)}
          >
            <span className="nome-arquivo">{nota.arquivo}</span>
            <span className="tipo">{nota.dados?.tipo_documento ?? '—'}</span>
            <span className={`status status-${nota.status}`}>{ROTULOS_STATUS[nota.status] ?? nota.status}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
