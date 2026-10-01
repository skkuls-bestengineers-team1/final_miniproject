import { useState } from 'react'
import { ChatWindow, QUICK_PROMPTS } from './components/ChatWindow'
import { BotMark } from './components/BotMark'
import './App.css'

const USERS = [
  { id: 'U001', name: '박종석' },
  { id: 'U002', name: '김하늘' },
]

const NAV = [
  '스스로해결',
  '전문상담',
  '서비스 안내',
  '서비스 예약',
  '고객의 소리',
]

export default function App() {
  const [userId, setUserId] = useState('U001')
  const [seedPrompt, setSeedPrompt] = useState<string | null>(null)
  const user = USERS.find((item) => item.id === userId) ?? USERS[0]

  return (
    <div className="shell">
      <div className="promo">
        공부용 상담 데모입니다. 기본 사용자는 {USERS[0].name}({USERS[0].id})입니다.
      </div>
      <header className="topbar">
        <a className="logo" href="#chat">
          <span className="wordmark">SASUNG</span>
          <span>사성전자서비스</span>
        </a>
        <nav>
          {NAV.map((item) => (
            <a
              key={item}
              href="#chat"
              className={item === '전문상담' ? 'current' : undefined}
            >
              {item}
            </a>
          ))}
        </nav>
        <label className="user-pick">
          사용자
          <select
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            aria-label="사용자 선택"
          >
            {USERS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.id})
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="hero">
        <p className="kicker">사성 CS Bot 시작</p>
        <h1>
          <span>신속한 상담</span>
          <span>고객 편의</span>
          <em>사성 CS Bot</em>
        </h1>
        <ChatWindow
          userId={user.id}
          userName={user.name}
          seedPrompt={seedPrompt}
          onSeedConsumed={() => setSeedPrompt(null)}
        />
        <h2 className="features-title">사성 CS Bot으로 확인해 보세요</h2>
      </section>

      <section className="features">
        <div className="feature-grid">
          <article>
            <h3>가까운 지점과 재고를 바로 확인할 수 있어요</h3>
            <p>강남역점 로봇청소기 재고, 내 주소 기준 가까운 센터를 한 번에 물어보세요.</p>
            <button type="button" onClick={() => setSeedPrompt(QUICK_PROMPTS[1])}>
              {QUICK_PROMPTS[1]}
            </button>
          </article>
          <article>
            <h3>주문 내역과 배송·교환도 이어서 진행할 수 있어요</h3>
            <p>주문 카드에서 상태·배송지를 확인하고, 교환·환불도 같은 창에서 이어갑니다.</p>
            <button type="button" onClick={() => setSeedPrompt(QUICK_PROMPTS[2])}>
              {QUICK_PROMPTS[2]}
            </button>
          </article>
        </div>
      </section>

      <button
        type="button"
        className="fab"
        onClick={() => document.getElementById('chat')?.scrollIntoView({ behavior: 'smooth' })}
      >
        <BotMark size={36} />
        <span>사성 CS Bot에게 궁금한 점을 물어보세요.</span>
      </button>

      <footer>
        사성전자 고객상담 멀티에이전트 데모 · 로그인 없이 user_id로 세션을 구분합니다.
      </footer>
    </div>
  )
}
