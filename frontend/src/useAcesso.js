import { useEffect, useState } from 'react'
import * as api from './api.js'

/** Se a pessoa já digitou a senha de acesso (e o token ainda vale). */
export function useAcesso() {
  const [autenticado, setAutenticado] = useState(api.temAcesso)
  useEffect(() => api.aoMudarAcesso(setAutenticado), [])
  return { autenticado, entrar: api.entrar, sair: api.sair }
}
