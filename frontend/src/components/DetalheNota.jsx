const moeda = (valor) =>
  valor == null ? '—' : valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

function baixarJson(nota) {
  const blob = new Blob([JSON.stringify(nota.dados, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${nota.arquivo.replace(/\.pdf$/i, '')}.json`
  link.click()
  URL.revokeObjectURL(url)
}

export default function DetalheNota({ nota }) {
  if (nota.status === 'pendente') return <div className="cartao">Processando {nota.arquivo}...</div>
  if (nota.status === 'erro') return <div className="cartao alerta-erro">{nota.erro}</div>

  const { dados, validacao, metadados } = nota
  const emitente = dados.emitente

  return (
    <div className="cartao detalhe">
      <div className="detalhe-topo">
        <h2>
          {dados.tipo_documento} nº {dados.numero ?? '—'}
          {dados.serie && <small> · série {dados.serie}</small>}
        </h2>
        <button onClick={() => baixarJson(nota)}>Baixar JSON</button>
      </div>

      <dl className="campos">
        <dt>Emitente</dt>
        <dd>{emitente.razao_social ?? '—'}</dd>
        <dt>CNPJ/CPF</dt>
        <dd>{emitente.cnpj ?? emitente.cpf ?? '—'}</dd>
        <dt>Data de emissão</dt>
        <dd>{dados.data_emissao ?? '—'}</dd>
        <dt>Chave de acesso</dt>
        <dd className="mono">{dados.chave_acesso ?? '—'}</dd>
        <dt>Valor total</dt>
        <dd><strong>{moeda(dados.valor_total_nota)}</strong></dd>
      </dl>

      <h3>Itens ({dados.itens.length})</h3>
      <div className="tabela-rolagem">
        <table>
          <thead>
            <tr>
              <th>Descrição</th>
              <th>Qtd.</th>
              <th>Valor unit.</th>
              <th>Valor total</th>
            </tr>
          </thead>
          <tbody>
            {dados.itens.map((item, i) => (
              <tr key={i}>
                <td>{item.descricao}</td>
                <td>{item.quantidade ?? '—'} {item.unidade ?? ''}</td>
                <td>{moeda(item.valor_unitario)}</td>
                <td>{moeda(item.valor_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Impostos</h3>
      <dl className="campos">
        {Object.entries(dados.impostos)
          .filter(([, valor]) => valor != null)
          .map(([nome, valor]) => (
            <div key={nome} className="campo-par">
              <dt>{nome.replace('valor_', '').replaceAll('_', ' ').toUpperCase()}</dt>
              <dd>{moeda(valor)}</dd>
            </div>
          ))}
      </dl>

      <h3>Validação fiscal</h3>
      <p>
        Pontuação: <strong>{Math.round(validacao.pontuacao * 100)}%</strong>
        {validacao.valido ? ' · todas as verificações passaram' : ''}
      </p>
      {validacao.erros.length > 0 && (
        <ul className="erros-validacao">
          {validacao.erros.map((erro) => (
            <li key={erro}>{erro}</li>
          ))}
        </ul>
      )}

      <p className="metadados">
        {metadados.modelo} · abordagem {metadados.abordagem} · {(metadados.tempo_ms / 1000).toFixed(1)} s ·{' '}
        {metadados.tokens_entrada} tokens de entrada / {metadados.tokens_saida} de saída
      </p>

      <details>
        <summary>JSON completo</summary>
        <pre>{JSON.stringify(dados, null, 2)}</pre>
      </details>
    </div>
  )
}
