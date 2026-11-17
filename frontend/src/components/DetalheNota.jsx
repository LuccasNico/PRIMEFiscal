import { useState } from 'react'
import { urlDoPdf } from '../api.js'
import {
  chaveDeAcesso,
  cnpjOuCpf,
  dataBrasileira,
  endereco,
  moeda,
  naFila,
  quantidade,
  ROTULOS_ABORDAGEM,
  ROTULOS_STATUS,
} from '../formatos.js'
import BotaoConfirmar from './BotaoConfirmar.jsx'
import { Girando } from './Icones.jsx'

const ROTULOS_VERIFICACAO = {
  tipo_identificado: 'Tipo de documento identificado',
  cnpj_emitente: 'CNPJ do emitente',
  cpf_emitente: 'CPF do emitente',
  documento_emitente: 'CNPJ/CPF do emitente',
  cnpj_destinatario: 'CNPJ do destinatário',
  cpf_destinatario: 'CPF do destinatário',
  chave_acesso: 'Chave de acesso',
  data_emissao: 'Data de emissão',
  itens_extraidos: 'Itens extraídos',
  itens_qtd_x_valor: 'Quantidade × valor unitário dos itens',
  soma_itens: 'Soma dos itens = total dos produtos',
  valor_total_nota: 'Valor total da nota',
}

const ROTULOS_IMPOSTO = {
  base_calculo_icms: 'Base de cálculo do ICMS',
  valor_icms: 'ICMS',
  valor_icms_st: 'ICMS ST',
  valor_ipi: 'IPI',
  valor_pis: 'PIS',
  valor_cofins: 'COFINS',
  valor_iss: 'ISS',
  valor_ibs: 'IBS',
  valor_cbs: 'CBS',
  valor_aproximado_tributos: 'Tributos aproximados',
}

function baixarJson(nota) {
  const blob = new Blob([JSON.stringify(nota.dados, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${nota.arquivo.replace(/\.pdf$/i, '')}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function Campo({ rotulo, children, mono }) {
  return (
    <div className="campo-par">
      <dt>{rotulo}</dt>
      <dd className={mono ? 'mono' : ''}>{children}</dd>
    </div>
  )
}

function Participante({ titulo, participante }) {
  if (!participante) return null
  return (
    <>
      <h3>{titulo}</h3>
      <dl className="campos">
        <Campo rotulo="Nome">{participante.razao_social ?? '—'}</Campo>
        <Campo rotulo="CNPJ/CPF">{cnpjOuCpf(participante)}</Campo>
        {participante.inscricao_estadual && <Campo rotulo="Inscrição estadual">{participante.inscricao_estadual}</Campo>}
        {participante.inscricao_municipal && (
          <Campo rotulo="Inscrição municipal">{participante.inscricao_municipal}</Campo>
        )}
        <Campo rotulo="Endereço">{endereco(participante)}</Campo>
      </dl>
    </>
  )
}

function DadosExtraidos({ nota }) {
  const { dados, validacao, metadados } = nota
  const impostos = Object.entries(dados.impostos ?? {}).filter(([, valor]) => valor != null)

  return (
    <div className="dados-extraidos">
      <dl className="campos">
        <Campo rotulo="Tipo">{dados.tipo_documento}</Campo>
        <Campo rotulo="Número / série">
          {dados.numero ?? '—'} / {dados.serie ?? '—'}
        </Campo>
        <Campo rotulo="Data de emissão">{dataBrasileira(dados.data_emissao)}</Campo>
        <Campo rotulo="Chave de acesso" mono>
          {chaveDeAcesso(dados.chave_acesso)}
        </Campo>
      </dl>

      <Participante titulo="Emitente" participante={dados.emitente} />
      <Participante titulo="Destinatário" participante={dados.destinatario} />

      <h3>Itens ({dados.itens.length})</h3>
      {dados.itens.length > 0 ? (
        <div className="tabela-rolagem">
          <table>
            <thead>
              <tr>
                <th>Código</th>
                <th>Descrição</th>
                <th className="numero">Qtd.</th>
                <th className="numero">Valor unit.</th>
                <th className="numero">Valor total</th>
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((item, indice) => (
                <tr key={indice}>
                  <td className="mono">{item.codigo ?? '—'}</td>
                  <td>{item.descricao}</td>
                  <td className="numero">
                    {quantidade(item.quantidade)} {item.unidade ?? ''}
                  </td>
                  <td className="numero">{moeda(item.valor_unitario)}</td>
                  <td className="numero">{moeda(item.valor_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="secundario">Nenhum item foi extraído.</p>
      )}

      <h3>Totais e impostos</h3>
      <dl className="campos">
        <Campo rotulo="Total dos produtos/serviços">{moeda(dados.valor_total_produtos)}</Campo>
        {dados.valor_desconto != null && <Campo rotulo="Desconto">{moeda(dados.valor_desconto)}</Campo>}
        {dados.valor_frete != null && <Campo rotulo="Frete">{moeda(dados.valor_frete)}</Campo>}
        {impostos.map(([nome, valor]) => (
          <Campo key={nome} rotulo={ROTULOS_IMPOSTO[nome] ?? nome}>
            {moeda(valor)}
          </Campo>
        ))}
        <Campo rotulo="Total da nota">
          <strong>{moeda(dados.valor_total_nota)}</strong>
        </Campo>
      </dl>

      {dados.pagamentos?.length > 0 && (
        <>
          <h3>Pagamento</h3>
          <dl className="campos">
            {dados.pagamentos.map((pagamento, indice) => (
              <Campo key={indice} rotulo={pagamento.forma}>
                {moeda(pagamento.valor)}
              </Campo>
            ))}
          </dl>
        </>
      )}

      {dados.informacoes_complementares && (
        <>
          <h3>Informações complementares</h3>
          <p className="texto-livre">{dados.informacoes_complementares}</p>
        </>
      )}

      {validacao && (
        <>
          <h3>
            Validação fiscal: {Math.round(validacao.pontuacao * 100)}%
            {validacao.valido && <span className="secundario"> · todas as verificações passaram</span>}
          </h3>
          <ul className="verificacoes">
            {Object.entries(validacao.verificacoes).map(([nome, passou]) => (
              <li key={nome} className={passou ? 'passou' : 'falhou'}>
                <span aria-hidden="true">{passou ? '✓' : '✕'}</span> {ROTULOS_VERIFICACAO[nome] ?? nome}
                <span className="sr-only">{passou ? ' (passou)' : ' (falhou)'}</span>
              </li>
            ))}
          </ul>
          {validacao.erros.length > 0 && (
            <ul className="erros-validacao">
              {validacao.erros.map((erro, indice) => (
                <li key={indice}>{erro}</li>
              ))}
            </ul>
          )}
        </>
      )}

      {metadados && (
        <p className="metadados">
          Extraído por {[metadados.provedor, metadados.modelo].filter(Boolean).join(' · ')} ·{' '}
          {ROTULOS_ABORDAGEM[metadados.abordagem] ?? metadados.abordagem} · {(metadados.tempo_ms / 1000).toFixed(1)} s
          {metadados.tokens_entrada != null &&
            ` · ${metadados.tokens_entrada} tokens de entrada, ${metadados.tokens_saida ?? '?'} de saída`}
        </p>
      )}

      <details>
        <summary>JSON completo</summary>
        <pre>{JSON.stringify(dados, null, 2)}</pre>
      </details>
    </div>
  )
}

/** Dados de uma nota, com as ações disponíveis e o PDF original ao lado para conferência. */
export default function DetalheNota({ nota, posicaoNaFila, aoReprocessar, aoRemover }) {
  const [mostrarPdf, setMostrarPdf] = useState(false)
  const [abordagem, setAbordagem] = useState(nota.abordagem ?? 'texto')

  const emFila = naFila(nota)
  const processando = nota.status === 'processando'
  const titulo = nota.dados
    ? `${nota.dados.tipo_documento}${nota.dados.numero ? ` nº ${nota.dados.numero}` : ''}`
    : nota.arquivo

  return (
    <section className="cartao detalhe" aria-labelledby="titulo-detalhe">
      <div className="detalhe-topo">
        <div>
          <h2 id="titulo-detalhe">
            {titulo} <span className={`status status-${nota.status}`}>{ROTULOS_STATUS[nota.status]}</span>
          </h2>
          {nota.dados && <p className="secundario">{nota.arquivo}</p>}
        </div>

        <div className="acoes">
          {nota.dados && !emFila && (
            <button type="button" onClick={() => baixarJson(nota)}>
              Baixar JSON
            </button>
          )}
          {nota.tem_pdf && (
            <button type="button" aria-pressed={mostrarPdf} onClick={() => setMostrarPdf(!mostrarPdf)}>
              {mostrarPdf ? 'Ocultar PDF' : 'Ver PDF'}
            </button>
          )}
          <BotaoConfirmar
            aoConfirmar={() => aoRemover(nota.id)}
            rotuloConfirmar={emFila ? 'Remover da fila?' : 'Excluir nota?'}
            disabled={processando}
            title={processando ? 'Em processamento: aguarde a conclusão para remover' : undefined}
          >
            {emFila ? 'Remover da fila' : 'Excluir'}
          </BotaoConfirmar>
        </div>
      </div>

      {nota.tem_pdf && !emFila && (
        <div className="reprocessar">
          <label htmlFor="abordagem-reprocessar">Reprocessar com</label>
          <select id="abordagem-reprocessar" value={abordagem} onChange={(evento) => setAbordagem(evento.target.value)}>
            <option value="texto">{ROTULOS_ABORDAGEM.texto}</option>
            <option value="pdf">{ROTULOS_ABORDAGEM.pdf}</option>
          </select>
          <button type="button" onClick={() => aoReprocessar(nota.id, abordagem)}>
            Reprocessar
          </button>
        </div>
      )}

      <div className={mostrarPdf && nota.tem_pdf ? 'comparacao' : ''}>
        {mostrarPdf && nota.tem_pdf && (
          <div className="visualizador-pdf">
            <iframe src={urlDoPdf(nota.id)} title={`PDF original: ${nota.arquivo}`} />
            <a href={urlDoPdf(nota.id)} target="_blank" rel="noreferrer">
              Abrir o PDF em outra aba
            </a>
          </div>
        )}

        <div>
          {nota.status === 'pendente' && (
            <p className="situacao">
              Na fila, aguardando a vez{posicaoNaFila ? ` (${posicaoNaFila}º da fila)` : ''}. Os dados aparecem aqui
              assim que a extração terminar.
            </p>
          )}
          {processando && (
            <p className="situacao">
              <Girando /> A IA está lendo esta nota. Os dados aparecem aqui assim que a extração terminar.
            </p>
          )}
          {nota.status === 'erro' && (
            <div className="alerta" role="alert">
              <strong>A extração falhou.</strong> {nota.erro}
              {nota.dados && ' Os dados abaixo são da extração anterior.'}
            </div>
          )}
          {nota.dados && !emFila && <DadosExtraidos nota={nota} />}
        </div>
      </div>
    </section>
  )
}
