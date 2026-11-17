import { useRef, useState } from 'react'
import { ROTULOS_ABORDAGEM, tamanhoDoArquivo } from '../formatos.js'
import { IconeEnviar, IconeFechar } from './Icones.jsx'

const ehPdf = (arquivo) => arquivo.type === 'application/pdf' || arquivo.name.toLowerCase().endsWith('.pdf')
const chave = (arquivo) => `${arquivo.name}-${arquivo.size}`

/** Escolha dos arquivos: eles ficam em uma lista de conferência e só vão para a fila quando a pessoa confirma. */
export default function AreaUpload({ aoEnviar, tamanhoMaximoMb, pdfExigeVisao }) {
  const [arquivos, setArquivos] = useState([])
  const [abordagem, setAbordagem] = useState('texto')
  const [arrastando, setArrastando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [avisos, setAvisos] = useState([])
  const inputRef = useRef(null)

  function adicionar(lista) {
    const novos = Array.from(lista)
    const pdfs = novos.filter(ehPdf)
    const limite = tamanhoMaximoMb ? tamanhoMaximoMb * 1024 * 1024 : Infinity
    const aceitos = pdfs.filter((arquivo) => arquivo.size <= limite)

    const novosAvisos = []
    if (novos.length > pdfs.length) {
      novosAvisos.push(`${novos.length - pdfs.length} arquivo(s) ignorado(s): apenas PDF é aceito.`)
    }
    if (pdfs.length > aceitos.length) {
      novosAvisos.push(`${pdfs.length - aceitos.length} arquivo(s) ignorado(s): acima de ${tamanhoMaximoMb} MB.`)
    }
    setAvisos(novosAvisos)

    // Evita adicionar o mesmo arquivo duas vezes
    setArquivos((atuais) => {
      const existentes = new Set(atuais.map(chave))
      return [...atuais, ...aceitos.filter((arquivo) => !existentes.has(chave(arquivo)))]
    })
  }

  async function enviar() {
    setEnviando(true)
    const enviados = await aoEnviar(arquivos, abordagem)
    // Em caso de erro, os arquivos que não foram aceitos continuam na lista para nova tentativa
    setArquivos((atuais) => atuais.slice(enviados))
    setAvisos([])
    setEnviando(false)
  }

  return (
    <section className="cartao" aria-labelledby="titulo-envio">
      <h2 id="titulo-envio">Enviar notas fiscais</h2>

      <button
        type="button"
        className={`area-upload ${arrastando ? 'arrastando' : ''}`}
        disabled={enviando}
        onClick={() => inputRef.current?.click()}
        onDragOver={(evento) => {
          evento.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(evento) => {
          evento.preventDefault()
          setArrastando(false)
          if (!enviando) adicionar(evento.dataTransfer.files)
        }}
      >
        <strong>Arraste os PDFs aqui</strong>
        <span className="dica">ou clique para escolher os arquivos</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(evento) => {
          adicionar(evento.target.files)
          evento.target.value = ''
        }}
      />

      {avisos.map((aviso) => (
        <p key={aviso} className="aviso">
          {aviso}
        </p>
      ))}

      {arquivos.length > 0 && (
        <>
          <div className="cabecalho-lista">
            <h3>Selecionados ({arquivos.length})</h3>
            <button type="button" className="link" onClick={() => setArquivos([])} disabled={enviando}>
              Limpar
            </button>
          </div>
          <ul className="lista lista-rolavel">
            {arquivos.map((arquivo) => (
              <li key={chave(arquivo)} className="linha">
                <span className="nome-arquivo" title={arquivo.name}>
                  {arquivo.name}
                </span>
                <span className="secundario">{tamanhoDoArquivo(arquivo.size)}</span>
                <button
                  type="button"
                  className="botao-icone"
                  onClick={() => setArquivos((atuais) => atuais.filter((a) => a !== arquivo))}
                  disabled={enviando}
                  aria-label={`Remover ${arquivo.name} da seleção`}
                  title="Remover da seleção"
                >
                  <IconeFechar />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <label className="campo">
        Como a IA deve ler a nota
        <select value={abordagem} onChange={(evento) => setAbordagem(evento.target.value)} disabled={enviando}>
          <option value="texto">{ROTULOS_ABORDAGEM.texto} (mais rápido, exige PDF com texto)</option>
          <option value="pdf">
            {ROTULOS_ABORDAGEM.pdf} ({pdfExigeVisao ? 'exige modelo com visão' : 'funciona com notas escaneadas'})
          </option>
        </select>
      </label>

      <button type="button" className="primario largo" onClick={enviar} disabled={!arquivos.length || enviando}>
        <IconeEnviar />
        {enviando
          ? 'Enviando...'
          : arquivos.length > 1
            ? `Adicionar ${arquivos.length} notas à fila`
            : 'Adicionar à fila'}
      </button>
    </section>
  )
}
