type BotMarkProps = {
  size?: number
}

export function BotMark({ size = 88 }: BotMarkProps) {
  return (
    <svg
      className="bot-mark"
      width={size}
      height={size}
      viewBox="0 0 88 88"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="botGlow" x1="12" y1="8" x2="76" y2="80">
          <stop offset="0%" stopColor="#7af0ff" />
          <stop offset="55%" stopColor="#4d7cff" />
          <stop offset="100%" stopColor="#8ea4ff" />
        </linearGradient>
      </defs>
      <circle cx="44" cy="44" r="36" fill="url(#botGlow)" opacity="0.28" />
      <path
        d="M44 16 L50.4 37.6 L72 44 L50.4 50.4 L44 72 L37.6 50.4 L16 44 L37.6 37.6 Z"
        fill="#fff"
      />
      <circle cx="44" cy="44" r="6.5" fill="#3b6cff" />
    </svg>
  )
}
