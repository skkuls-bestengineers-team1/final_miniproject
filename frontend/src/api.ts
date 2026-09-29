export type ChatResponse = {
  answer: string
  waiting_approval: boolean
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function sendMessage(userId: string, message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
    body: JSON.stringify({
      user_id: userId,
      message,
    }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || '상담 서버에 연결하지 못했습니다.')
  }

  return response.json()
}

export async function fetchNotifications(userId: string) {
  const response = await fetch(`${API_BASE}/notifications/${userId}`)

  if (!response.ok) {
    throw new Error('알림을 가져오지 못했습니다.')
  }

  return response.json()
}
