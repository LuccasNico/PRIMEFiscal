function Icone({ children }) {
  return (
    <svg
      className="icone"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const IconeFechar = () => (
  <Icone>
    <path d="M18 6 6 18M6 6l12 12" />
  </Icone>
)

export const IconeLixeira = () => (
  <Icone>
    <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
  </Icone>
)

export const IconeRepetir = () => (
  <Icone>
    <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5" />
  </Icone>
)

export const IconeEnviar = () => (
  <Icone>
    <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
  </Icone>
)

export const Girando = () => <span className="girando" role="img" aria-label="Processando" />
