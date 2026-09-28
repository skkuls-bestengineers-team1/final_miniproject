export type ChatMessage = {
  role: 'user' | 'bot'
  text: string
}

type MessageBubbleProps = {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <div className={`bubble ${message.role}`}>
      {message.text}
    </div>
  )
}
