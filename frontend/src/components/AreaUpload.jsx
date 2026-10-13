import { useRef, useState } from 'react'

export default function AreaUpload({ aoEnviar, enviando }) {
  const [arrastando, setArrastando] = useState(false)
  const [abordagem, setAbordagem] = useState('pdf')
  const inputRef = useRef(null)

  function enviar(listaArquivos) {
    const pdfs = Array.from(listaArquivos).filter((a) => a.type === 'application/pdf')
    if (pdfs.length) aoEnviar(pdfs, abordagem)
  }

  return (
    <div className="cartao">
      <div
        className={`area-upload ${arrastando ? 'arrastando' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastando(false)
          enviar(e.dataTransfer.files)
        }}
      >
        {enviando ? (
          <p>Processando com IA...</p>
        ) : (
          <>
            <p><strong>Arraste PDFs de notas fiscais aqui</strong></p>
            <p className="dica">ou clique para selecionar (vários arquivos = lote)</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          hidden
          onChange={(e) => {
            enviar(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      <label className="seletor">
        Abordagem:
        <select value={abordagem} onChange={(e) => setAbordagem(e.target.value)} disabled={enviando}>
          <option value="pdf">PDF direto no Claude</option>
          <option value="texto">Texto extraído (pdfplumber) + Claude</option>
        </select>
      </label>
    </div>
  )
}
