import { FormEvent, useEffect, useRef, useState } from 'react'
import type { ChatStoreCard } from '../api'
import { Position, SendOptions, sendMessage } from '../api'
import { BotMark } from './BotMark'
import { ChatMessage, MessageBubble } from './MessageBubble'
import { ReservationModal } from './ReservationModal'

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

const ADDRESS_PLACEHOLDER = '역이나 동 이름을 입력해 주세요. (예: 용산역)'

// 브라우저 현재 위치. 권한 거부·시간 초과·미지원이면 null.
function currentPosition(): Promise<Position | null> {
  return new Promise((resolve) => {
    if (!('geolocation' in navigator)) {
      resolve(null)
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      }),
      () => resolve(null),
      { timeout: 10000, maximumAge: 5 * 60 * 1000 },
    )
  })
}

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
  const [askOrigin, setAskOrigin] = useState(false)
  const [addressMode, setAddressMode] = useState(false)
  const [locating, setLocating] = useState(false)
  const [reserveStore, setReserveStore] = useState<ChatStoreCard | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const sendingRef = useRef(false)

  useEffect(() => {
    setActive(false)
    setMessages([])
    setDraft('')
    setWaitingApproval(false)
    setAskOrigin(false)
    setAddressMode(false)
    setLocating(false)
    setReserveStore(null)
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

  async function ask(text: string, options: SendOptions = {}) {
    const trimmed = text.trim()

    if (!trimmed || sendingRef.current) {
      return
    }

    const started = active
    sendingRef.current = true
    setActive(true)
    setDraft('')
    setSending(true)
    setAskOrigin(false)
    setAddressMode(false)
    setMessages((current) => {
      const next = started ? current : [{ role: 'bot', text: GREETING, time: clock() } as ChatMessage]
      return [...next, { role: 'user', text: trimmed, time: clock() }]
    })

    try {
      const result = await sendMessage(userId, trimmed, options)
      setWaitingApproval(Boolean(result.waiting_approval))
      setAskOrigin(Boolean(result.ask_search_origin))
      const suffix = result.waiting_approval ? '\n\n관리자 승인을 기다리고 있습니다.' : ''

      setMessages((current) => [
        ...current,
        { role: 'bot', text: `${result.answer}${suffix}`, time: clock(), ui: result.ui },
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

  // 기준 위치 선택: 현재 위치. 권한을 거부하거나 실패하면 등록 주소로 대신한다.
  async function pickCurrentPosition() {
    if (sendingRef.current || locating) {
      return
    }

    setLocating(true)
    const position = await currentPosition()
    setLocating(false)

    if (position) {
      void ask('현재 위치 사용', { currentPosition: position })
      return
    }

    void ask('현재 위치를 가져오지 못해 등록 주소로 찾아 주세요', { useRegisteredAddress: true })
  }

  // 기준 위치 선택: 주소 입력. 입력한 문장은 일반 메시지로 보내고 서버가 주소로 해석한다.
  function startAddressInput() {
    setAddressMode(true)
    inputRef.current?.focus()
  }

  function pickRegisteredAddress() {
    void ask('등록 주소 사용', { useRegisteredAddress: true })
  }

  function resetChat() {
    setActive(false)
    setMessages([])
    setDraft('')
    setWaitingApproval(false)
    setAskOrigin(false)
    setAddressMode(false)
    setLocating(false)
    setReserveStore(null)
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
          <MessageBubble
            key={`${message.role}-${index}`}
            message={message}
            onReserve={(name) => {
              const found = (message.ui?.stores || []).find((store) => store.store_name === name)
              if (found) {
                setReserveStore(found)
              }
            }}
          />
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
      {askOrigin && !sending ? (
        <div className="origin-pick" role="group" aria-label="기준 위치 선택">
          <button type="button" onClick={() => void pickCurrentPosition()} disabled={locating}>
            {locating ? '위치 확인 중…' : '현재 위치 사용'}
          </button>
          <button
            type="button"
            onClick={startAddressInput}
            className={addressMode ? 'selected' : undefined}
            aria-pressed={addressMode}
          >
            주소 입력
          </button>
          <button type="button" onClick={pickRegisteredAddress} disabled={locating}>
            등록 주소로
          </button>
        </div>
      ) : null}
      <form className="pill-form dock" onSubmit={onSubmit}>
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={askOrigin && addressMode ? ADDRESS_PLACEHOLDER : '메시지를 입력해 주세요.'}
          aria-label="문의 입력"
          disabled={sending || locating}
        />
        <button type="submit" disabled={sending || locating || !draft.trim()} aria-label="전송">
          <SendIcon />
        </button>
      </form>
      <p className="disclaimer">
        AI가 만든 답변은 부정확할 수 있습니다. · 위치 검색{' '}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          © OpenStreetMap contributors
        </a>
      </p>
      {reserveStore ? (
        <ReservationModal store={reserveStore} onClose={() => setReserveStore(null)} />
      ) : null}
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
