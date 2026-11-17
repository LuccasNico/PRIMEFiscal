import { useState } from 'react'

/** Pede a senha de acesso por cima da interface, que continua montada (os arquivos escolhidos não se perdem). */
export default function TelaDeAcesso({ aoEntrar }) {
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState(null)
  const [entrando, setEntrando] = useState(false)

  async function entrar(evento) {
    evento.preventDefault()
    setEntrando(true)
    setErro(null)
    try {
      await aoEntrar(senha)
    } catch (e) {
      setErro(e.message)
      setEntrando(false)
    }
  }

  return (
    <div className="tela-acesso">
      <form className="cartao cartao-acesso" onSubmit={entrar} aria-labelledby="titulo-acesso">
        <img src="/icone.svg" alt="" width="56" height="56" />
        <h2 id="titulo-acesso">PRIMEFiscal</h2>
        <p className="secundario">Digite a senha de acesso para usar a extração com Inteligência Artificial.</p>
        <label className="campo">
          Senha de acesso
          <input
            type="password"
            autoComplete="current-password"
            autoFocus
            value={senha}
            onChange={(evento) => setSenha(evento.target.value)}
            disabled={entrando}
          />
        </label>
        {erro && (
          <p className="aviso erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="primario largo" disabled={!senha || entrando}>
          {entrando ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
