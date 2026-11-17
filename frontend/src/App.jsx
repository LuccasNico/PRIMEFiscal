import { useState } from 'react'
import AreaUpload from './components/AreaUpload.jsx'
import DetalheNota from './components/DetalheNota.jsx'
import FilaProcessamento from './components/FilaProcessamento.jsx'
import { IconeFechar } from './components/Icones.jsx'
import ListaNotas from './components/ListaNotas.jsx'
import SeletorDeModelo from './components/SeletorDeModelo.jsx'
import TelaDeAcesso from './components/TelaDeAcesso.jsx'
import { useAcesso } from './useAcesso.js'
import { useModelos } from './useModelos.js'
import { useNotas } from './useNotas.js'

function Cabecalho({ saude, escolhaDoModelo, aoSair }) {
  return (
    <header className="cabecalho">
      <div className="marca">
        <img src="/icone.svg" alt="" width="48" height="48" />
        <div>
          <h1>PRIMEFiscal</h1>
          <p>Extração de dados de notas fiscais com Inteligência Artificial</p>
        </div>
      </div>
      {saude && (
        <div className="provedor">
          <span>
            IA: <strong>{saude.nome_provedor}</strong>
          </span>
          {saude.escolhe_modelo ? (
            <SeletorDeModelo {...escolhaDoModelo} padrao={saude.modelo} />
          ) : (
            <span className="modelo-atual">{saude.modelo}</span>
          )}
          {aoSair && (
            <button type="button" className="link" onClick={aoSair}>
              Sair
            </button>
          )}
        </div>
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
  const { autenticado, entrar, sair } = useAcesso()
  const {
    notas,
    fila,
    concluidas,
    saude,
    bloqueado,
    erro,
    dispensarErro,
    enviar,
    remover,
    esvaziarFila,
    reprocessar,
    reprocessarVarias,
    salvarNoBanco,
  } = useNotas(autenticado)
  const exigeSenha = Boolean(saude?.exige_senha)
  const escolhaDoModelo = useModelos(Boolean(saude?.escolhe_modelo) && !bloqueado)
  const { modelo } = escolhaDoModelo
  const [selecionadaId, setSelecionadaId] = useState(null)

  const selecionada = notas.find((nota) => nota.id === selecionadaId)
  const aguardando = fila.filter((nota) => nota.status === 'pendente')
  const aoReprocessar = (id, abordagem) => reprocessar(id, abordagem, modelo)

  async function aoEnviar(arquivos, abordagem) {
    const { criadas, enviados } = await enviar(arquivos, abordagem, modelo)
    // Abre a nota recém-enviada quando é uma só ou quando não há outra em exibição
    if (criadas.length && (criadas.length === 1 || !selecionada)) setSelecionadaId(criadas[0].id)
    return enviados
  }

  return (
    <>
      {/* inert: com a tela de senha aberta, a interface por trás não recebe foco nem cliques */}
      <div className="app" inert={bloqueado}>
        <Cabecalho saude={saude} escolhaDoModelo={escolhaDoModelo} aoSair={exigeSenha && autenticado ? sair : null} />

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
              aoReprocessar={aoReprocessar}
              aoReprocessarVarias={(ids) => reprocessarVarias(ids, modelo)}
            />
          </div>

          <div className="coluna-direita">
            {selecionada ? (
              <DetalheNota
                key={selecionada.id}
                nota={selecionada}
                posicaoNaFila={aguardando.indexOf(selecionada) + 1}
                aoReprocessar={aoReprocessar}
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
      {bloqueado && <TelaDeAcesso aoEntrar={entrar} />}
    </>
  )
}
