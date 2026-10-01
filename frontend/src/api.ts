export type ChatStoreCard = {
  rank: number
  store_name: string
  distance_km: number | null
  address: string
  lat: number | null
  lng: number | null
  photo_url: string
}

export type ChatProductCard = {
  store_name: string
  product_code: string
  product_name: string
  category: string
  quantity: number
  price: number | null
  photo_url: string
}

export type ChatOrderCard = {
  order_id: string
  product_name: string
  product_code: string
  option: string
  order_date: string
  expected_date: string
  delivered_date: string
  delivery_status: string
  delivery_status_label: string
  ship_address: string
  price: number | null
  photo_url: string
}

export type ChatUi = {
  stores?: ChatStoreCard[]
  products?: ChatProductCard[]
  orders?: ChatOrderCard[]
}

export type ChatResponse = {
  answer: string
  waiting_approval: boolean
  ask_search_origin?: boolean
  ui?: ChatUi | null
}

// 가까운 지점 검색 기준점. 주문·배송 주소와는 별개다.
export type Position = {
  lat: number
  lng: number
}

export type SendOptions = {
  currentPosition?: Position
  useRegisteredAddress?: boolean
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function sendMessage(
  userId: string,
  message: string,
  options: SendOptions = {},
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
    body: JSON.stringify({
      user_id: userId,
      message,
      current_position: options.currentPosition ?? null,
      use_registered_address: options.useRegisteredAddress ?? false,
    }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || '상담 서버에 연결하지 못했습니다.')
  }

  return response.json()
}

export async function resetChatSession(userId: string) {
  await fetch(`${API_BASE}/chat/reset`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
    body: JSON.stringify({ user_id: userId }),
  })
}

export type Reservation = {
  reservation_id: number
  user_id: string
  store_id: string
  store_name: string
  store_address: string | null
  visit_date: string
  visit_time: string
  status: string
  created_at: string
  cancelled_at: string | null
}

// 서버가 400/404로 돌려준 detail(안내 문구)을 그대로 보여 준다.
async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}

export async function createReservation(
  userId: string,
  storeName: string,
  visitDate: string,
  visitTime: string,
): Promise<Reservation> {
  const response = await fetch(`${API_BASE}/reservations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
    body: JSON.stringify({
      user_id: userId,
      store_name: storeName,
      visit_date: visitDate,
      visit_time: visitTime,
    }),
  })

  if (!response.ok) {
    throw new Error(await errorDetail(response, '예약을 접수하지 못했습니다.'))
  }

  return response.json()
}

export async function cancelReservation(userId: string, reservationId: number): Promise<Reservation> {
  const response = await fetch(`${API_BASE}/reservations/${reservationId}/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
    body: JSON.stringify({ user_id: userId }),
  })

  if (!response.ok) {
    throw new Error(await errorDetail(response, '예약을 취소하지 못했습니다.'))
  }

  return response.json()
}

export async function fetchReservations(userId: string): Promise<Reservation[]> {
  const response = await fetch(`${API_BASE}/reservations/${userId}`)

  if (!response.ok) {
    throw new Error('예약 내역을 가져오지 못했습니다.')
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
