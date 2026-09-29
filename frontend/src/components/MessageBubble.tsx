export type ChatMessage = {
  role: 'user' | 'bot'
  text: string
  time?: string
}

type MessageBubbleProps = {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="row user">
        <div className="bubble user">{message.text}</div>
        {message.time ? <time>{message.time}</time> : null}
      </div>
    )
  }

  return (
    <div className="row bot">
      <div className="bot-face" aria-hidden="true">✧</div>
      <div>
        <div className="bubble bot">{message.text}</div>
        {message.time ? <time>{message.time}</time> : null}
      </div>
    </div>
  )
}
