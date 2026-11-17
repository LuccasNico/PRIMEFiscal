import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_API_URL precisa ser a URL completa da API (ex.: https://primefiscal-api.onrender.com).
// Sem o https://, o navegador trata o valor como um caminho do próprio site e as chamadas dão 404.
function conferirUrlDaApi(url) {
  if (url && !/^https?:\/\/[^/]+/.test(url.trim())) {
    throw new Error(
      `VITE_API_URL inválida: "${url}". Use a URL completa da API, ` +
        'por exemplo https://primefiscal-api.onrender.com (não o nome do serviço).',
    )
  }
}

export default defineConfig(({ mode }) => {
  conferirUrlDaApi(loadEnv(mode, process.cwd(), 'VITE_').VITE_API_URL)
  return {
    plugins: [react()],
    server: {
      // Redireciona as chamadas /api para o backend FastAPI
      proxy: {
        '/api': 'http://localhost:8000',
      },
    },
  }
})
