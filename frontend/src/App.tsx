import { useState } from 'react'
import { ChatWindow } from './components/ChatWindow'
import './App.css'

export default function App() {
  const [userId, setUserId] = useState('U001')

  return (
    <main className="page">
      <header>
        <p className="brand">사성전자</p>
        <h1>고객상담</h1>
        <label>
          사용자
          <input
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            aria-label="사용자 ID"
          />
        </label>
      </header>
      <ChatWindow userId={userId} />
    </main>
  )
}
