import { FormEvent, useState } from 'react'
import { sendMessage } from '../api'
import { MessageBubble, ChatMessage } from './MessageBubble'

type ChatWindowProps = {
  userId: string
}

const GREETING = '안녕하세요. 사성전자 고객상담입니다. 무엇을 도와드릴까요?'

export function ChatWindow({ userId }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'bot', text: GREETING },
  ])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()

    const text = draft.trim()

    if (!text || sending) {
      return
    }

    setMessages((current) => [...current, { role: 'user', text }])
    setDraft('')
    setSending(true)

    try {
      const result = await sendMessage(userId, text)
      const suffix = result.waiting_approval ? '\n\n관리자 승인을 기다리고 있습니다.' : ''

      setMessages((current) => [
        ...current,
        { role: 'bot', text: `${result.answer}${suffix}` },
      ])
    } catch (error) {
      const message = error instanceof Error ? error.message : '전송에 실패했습니다.'

      setMessages((current) => [
        ...current,
        { role: 'bot', text: message },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="chat">
      <div className="log">
        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}
      </div>
      <form className="composer" onSubmit={onSubmit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="문의를 입력하세요"
          aria-label="문의 입력"
        />
        <button type="submit" disabled={sending}>
          {sending ? '전송 중' : '전송'}
        </button>
      </form>
    </section>
  )
}
