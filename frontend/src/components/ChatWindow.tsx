import { FormEvent, useEffect, useRef, useState } from 'react'
import { sendMessage } from '../api'
import { BotMark } from './BotMark'
import { ChatMessage, MessageBubble } from './MessageBubble'

type ChatWindowProps = {
  userId: string
  userName: string
  seedPrompt?: string | null
  onSeedConsumed?: () => void
}

export const QUICK_PROMPTS = [
  '가까운 지점 알려주세요',
  '강남역 로봇청소기 재고 알려주세요',
  '배송 상태 알려주세요',
  '배송지 변경하고 싶어요',
  '교환하고 싶어요',
  '색상이 달라서 반품하는데 배송비 누가 내요?',
]

const GREETING = '안녕하세요. 사성전자 고객상담입니다. 가까운 지점, 재고, 배송, 교환·환불 모두 도와드릴게요.'

function clock() {
  return new Date().toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function ChatWindow({
  userId,
  userName,
  seedPrompt,
  onSeedConsumed,
}: ChatWindowProps) {
  const [active, setActive] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [waitingApproval, setWaitingApproval] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const sendingRef = useRef(false)

  useEffect(() => {
    setActive(false)
    setMessages([])
    setDraft('')
    setWaitingApproval(false)
    sendingRef.current = false
    setSending(false)
  }, [userId])

  useEffect(() => {
    const node = logRef.current

    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [messages, sending, active])

  useEffect(() => {
    if (!seedPrompt) {
      return
    }

    void ask(seedPrompt)
    onSeedConsumed?.()
  }, [seedPrompt])

  async function ask(text: string) {
    const trimmed = text.trim()

    if (!trimmed || sendingRef.current) {
      return
    }

    const started = active
    sendingRef.current = true
    setActive(true)
    setDraft('')
    setSending(true)
    setMessages((current) => {
      const next = started ? current : [{ role: 'bot', text: GREETING, time: clock() } as ChatMessage]
      return [...next, { role: 'user', text: trimmed, time: clock() }]
    })

    try {
      const result = await sendMessage(userId, trimmed)
      setWaitingApproval(Boolean(result.waiting_approval))
      const suffix = result.waiting_approval ? '\n\n관리자 승인을 기다리고 있습니다.' : ''

      setMessages((current) => [
        ...current,
        { role: 'bot', text: `${result.answer}${suffix}`, time: clock() },
      ])
    } catch (error) {
      const message = error instanceof Error ? error.message : '전송에 실패했습니다.'

      setMessages((current) => [
        ...current,
        { role: 'bot', text: message, time: clock() },
      ])
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void ask(draft)
  }

  function resetChat() {
    setActive(false)
    setMessages([])
    setDraft('')
    setWaitingApproval(false)
    sendingRef.current = false
    setSending(false)
  }

  if (!active) {
    return (
      <section className="hero-card" id="chat">
        <div className="hero-mascot">
          <BotMark size={168} />
        </div>
        <div className="hero-copy">
          <p>
            {userName} 님, 사성 CS Bot으로 가까운 지점·재고·배송·교환·환불을
            바로 물어보세요.
          </p>
          <form className="pill-form" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="사성 CS Bot 에게 무엇이든 물어보세요"
              aria-label="문의 입력"
            />
            <button type="submit" disabled={sending || !draft.trim()} aria-label="전송">
              <SendIcon />
            </button>
          </form>
          <div className="chips">
            {QUICK_PROMPTS.map((prompt) => (
              <button key={prompt} type="button" onClick={() => void ask(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="hero-card chat-card" id="chat">
      <header className="chat-head">
        <div>
          <BotMark size={28} />
          <strong>사성 CS Bot</strong>
        </div>
        <button type="button" className="icon-btn" onClick={resetChat} aria-label="상담 닫기">
          ×
        </button>
      </header>
      <div className="log" ref={logRef}>
        {messages.map((message, index) => (
          <MessageBubble key={`${message.role}-${index}`} message={message} />
        ))}
        {sending ? (
          <div className="row bot">
            <div className="bot-face" aria-hidden="true">✧</div>
            <div className="bubble bot typing" aria-label="답변 작성 중">
              <span />
              <span />
              <span />
            </div>
          </div>
        ) : null}
      </div>
      {waitingApproval ? (
        <p className="notice">배송지 변경은 관리자 승인 후 이어집니다.</p>
      ) : null}
      <form className="pill-form dock" onSubmit={onSubmit}>
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="메시지를 입력해 주세요."
          aria-label="문의 입력"
          disabled={sending}
        />
        <button type="submit" disabled={sending || !draft.trim()} aria-label="전송">
          <SendIcon />
        </button>
      </form>
      <p className="disclaimer">AI가 만든 답변은 부정확할 수 있습니다.</p>
    </section>
  )
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M4 3.2 L15 9 L4 14.8 L4 10.2 L10.2 9 L4 7.8 Z" fill="currentColor" />
    </svg>
  )
}
