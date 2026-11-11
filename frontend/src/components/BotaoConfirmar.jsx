import { useEffect, useState } from 'react'

/**
 * Botão para ações que apagam dados: o primeiro clique pede confirmação no próprio botão
 * e só o segundo executa. Se a pessoa não confirmar em alguns segundos, volta ao normal.
 */
export default function BotaoConfirmar({ aoConfirmar, rotuloConfirmar = 'Confirmar?', className = '', children, ...props }) {
  const [armado, setArmado] = useState(false)

  useEffect(() => {
    if (!armado) return
    const temporizador = setTimeout(() => setArmado(false), 4000)
    return () => clearTimeout(temporizador)
  }, [armado])

  function aoClicar(evento) {
    evento.stopPropagation()
    if (armado) aoConfirmar()
    setArmado(!armado)
  }

  return (
    <button
      type="button"
      {...props}
      className={`${className} ${armado ? 'perigo' : ''}`}
      onClick={aoClicar}
      onBlur={() => setArmado(false)}
    >
      {armado ? rotuloConfirmar : children}
    </button>
  )
}
