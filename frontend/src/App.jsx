import { useState } from 'react'
import AreaUpload from './components/AreaUpload.jsx'
import DetalheNota from './components/DetalheNota.jsx'
import FilaProcessamento from './components/FilaProcessamento.jsx'
import { IconeFechar } from './components/Icones.jsx'
import ListaNotas from './components/ListaNotas.jsx'
import { useNotas } from './useNotas.js'

function Cabecalho({ saude }) {
  return (
    <header className="cabecalho">
      <div>
        <h1>PRIMEFiscal</h1>
        <p>Extração de dados de notas fiscais com Inteligência Artificial</p>
      </div>
      {saude && (
        <p className="provedor">
          IA: <strong>{saude.nome_provedor}</strong>
          <br />
          {saude.modelo}
        </p>
      )}
      {saude === null && (
        <p className="provedor erro" role="alert">
          Servidor fora do ar
          <br />
          Inicie o backend (porta 8000)
        </p>
      )}
    </header>
  )
}

export default function App() {
  const {
    notas,
    fila,
    concluidas,
    saude,
    erro,
    dispensarErro,
    enviar,
    remover,
    esvaziarFila,
    reprocessar,
    reprocessarVarias,
    salvarNoBanco,
  } = useNotas()
  const [selecionadaId, setSelecionadaId] = useState(null)

  const selecionada = notas.find((nota) => nota.id === selecionadaId)
  const aguardando = fila.filter((nota) => nota.status === 'pendente')

  async function aoEnviar(arquivos, abordagem) {
    const { criadas, enviados } = await enviar(arquivos, abordagem)
    // Abre a nota recém-enviada quando é uma só ou quando não há outra em exibição
    if (criadas.length && (criadas.length === 1 || !selecionada)) setSelecionadaId(criadas[0].id)
    return enviados
  }

  return (
    <div className="app">
      <Cabecalho saude={saude} />

      <main className="conteudo">
        <div className="coluna-esquerda">
          <AreaUpload
            aoEnviar={aoEnviar}
            tamanhoMaximoMb={saude?.tamanho_maximo_mb}
            pdfExigeVisao={saude?.pdf_exige_visao}
          />

          {erro && (
            <div className="alerta" role="alert">
              <span>{erro}</span>
              <button type="button" className="botao-icone" onClick={dispensarErro} aria-label="Fechar aviso">
                <IconeFechar />
              </button>
            </div>
          )}

          <FilaProcessamento
            fila={fila}
            selecionadaId={selecionadaId}
            aoSelecionar={setSelecionadaId}
            aoRemover={remover}
            aoEsvaziar={esvaziarFila}
          />

          <ListaNotas
            notas={concluidas}
            selecionadaId={selecionadaId}
            aoSelecionar={setSelecionadaId}
            aoRemover={remover}
            aoReprocessar={reprocessar}
            aoReprocessarVarias={reprocessarVarias}
          />
        </div>

        <div className="coluna-direita">
          {selecionada ? (
            <DetalheNota
              key={selecionada.id}
              nota={selecionada}
              posicaoNaFila={aguardando.indexOf(selecionada) + 1}
              aoReprocessar={reprocessar}
              aoRemover={remover}
              aoSalvarNoBanco={salvarNoBanco}
            />
          ) : (
            <p className="vazio">
              {notas.length
                ? 'Selecione uma nota para ver os dados extraídos.'
                : 'Envie uma nota fiscal em PDF para começar.'}
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
