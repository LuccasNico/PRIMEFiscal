import { useRef, useState } from 'react'

const formatarTamanho = (bytes) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

export default function AreaUpload({ aoEnviar, enviando }) {
  const [arquivos, setArquivos] = useState([])
  const [abordagem, setAbordagem] = useState('texto')
  const [arrastando, setArrastando] = useState(false)
  const [aviso, setAviso] = useState(null)
  const inputRef = useRef(null)

  function adicionar(lista) {
    const novos = Array.from(lista)
    const pdfs = novos.filter((a) => a.type === 'application/pdf' || a.name.toLowerCase().endsWith('.pdf'))
    const recusados = novos.length - pdfs.length
    setAviso(recusados ? `${recusados} arquivo(s) ignorado(s): apenas PDF é aceito.` : null)

    // Evita adicionar o mesmo arquivo duas vezes
    setArquivos((atuais) => {
      const chaves = new Set(atuais.map((a) => `${a.name}-${a.size}`))
      return [...atuais, ...pdfs.filter((a) => !chaves.has(`${a.name}-${a.size}`))]
    })
  }

  function remover(indice) {
    setArquivos((atuais) => atuais.filter((_, i) => i !== indice))
  }

  async function enviar() {
    // Em caso de erro, mantém os arquivos para o usuário tentar de novo
    if (await aoEnviar(arquivos, abordagem)) {
      setArquivos([])
      setAviso(null)
    }
  }

  return (
    <div className="cartao">
      <h2>Enviar nota fiscal</h2>

      <div
        className={`area-upload ${arrastando ? 'arrastando' : ''}`}
        onClick={() => !enviando && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastando(false)
          if (!enviando) adicionar(e.dataTransfer.files)
        }}
      >
        <p><strong>Arraste os PDFs aqui</strong></p>
        <p className="dica">ou clique para escolher os arquivos</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => {
            adicionar(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {aviso && <p className="aviso">{aviso}</p>}

      {arquivos.length > 0 && (
        <ul className="arquivos-selecionados">
          {arquivos.map((arquivo, i) => (
            <li key={`${arquivo.name}-${arquivo.size}`}>
              <span className="nome-arquivo" title={arquivo.name}>{arquivo.name}</span>
              <span className="tamanho">{formatarTamanho(arquivo.size)}</span>
              <button
                type="button"
                className="botao-remover"
                onClick={() => remover(i)}
                disabled={enviando}
                aria-label={`Remover ${arquivo.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <label className="seletor">
        Abordagem de extração
        <select value={abordagem} onChange={(e) => setAbordagem(e.target.value)} disabled={enviando}>
          <option value="texto">Texto extraído do PDF (mais rápido)</option>
          <option value="pdf">PDF/imagem da página (exige modelo com visão)</option>
        </select>
      </label>

      <div className="acoes">
        <button type="button" onClick={enviar} disabled={!arquivos.length || enviando}>
          {enviando
            ? 'Processando...'
            : arquivos.length > 1
              ? `Enviar ${arquivos.length} arquivos (lote)`
              : 'Enviar'}
        </button>
        {arquivos.length > 0 && !enviando && (
          <button type="button" className="secundario" onClick={() => setArquivos([])}>
            Limpar
          </button>
        )}
      </div>

      {enviando && <p className="dica">A extração pode levar alguns minutos com modelo local.</p>}
    </div>
  )
}
