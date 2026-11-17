/** Lista suspensa com os modelos do provedor de IA. Enquanto a lista não chega, mostra o modelo padrão. */
export default function SeletorDeModelo({ modelos, modelo, escolher, erro, carregando, padrao }) {
  if (!modelos.length) {
    return (
      <span className="modelo-atual" title={erro ? `Lista de modelos indisponível: ${erro}` : undefined}>
        {carregando ? 'Carregando modelos...' : padrao}
        {erro && <span className="aviso"> (padrão)</span>}
      </span>
    )
  }

  const descricao = modelos.find((item) => item.id === modelo)?.descricao
  return (
    <label className="seletor-modelo">
      <span className="sr-only">Modelo de IA usado nas próximas extrações</span>
      <select
        value={modelo}
        onChange={(evento) => escolher(evento.target.value)}
        title={[modelo, descricao].filter(Boolean).join(' — ')}
      >
        {modelos.map((item) => (
          <option key={item.id} value={item.id}>
            {item.nome}
          </option>
        ))}
      </select>
    </label>
  )
}
