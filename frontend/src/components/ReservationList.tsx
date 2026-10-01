import { useEffect, useState } from 'react'
import { cancelReservation, fetchReservations } from '../api'
import type { Reservation } from '../api'

type ReservationListProps = {
  userId: string
  userName: string
  onStartChat: () => void
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

function visitAt(item: Reservation) {
  return new Date(`${item.visit_date}T${item.visit_time}:00`)
}

// 2026-10-02 15:00 → 10월 2일 (금) 15:00
function formatVisit(item: Reservation) {
  const at = visitAt(item)
  return `${at.getMonth() + 1}월 ${at.getDate()}일 (${WEEKDAYS[at.getDay()]}) ${item.visit_time}`
}

function statusLabel(item: Reservation, past: boolean) {
  if (item.status === 'CANCELLED') {
    return '취소됨'
  }

  return past ? '방문 완료' : '예약 확정'
}

export function ReservationList({ userId, userName, onStartChat }: ReservationListProps) {
  const [items, setItems] = useState<Reservation[] | null>(null)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [cancelling, setCancelling] = useState<number | null>(null)

  async function onCancel(item: Reservation) {
    if (cancelling !== null) {
      return
    }

    if (!window.confirm(`${formatVisit(item)} ${item.store_name} 예약을 취소할까요?`)) {
      return
    }

    setCancelling(item.reservation_id)
    setError('')

    try {
      const updated = await cancelReservation(userId, item.reservation_id)
      setItems((current) =>
        (current ?? []).map((row) => (row.reservation_id === updated.reservation_id ? updated : row)),
      )
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '예약을 취소하지 못했습니다.')
    } finally {
      setCancelling(null)
    }
  }

  useEffect(() => {
    let alive = true
    setItems(null)
    setError('')

    fetchReservations(userId)
      .then((rows) => {
        if (alive) {
          setItems(rows)
        }
      })
      .catch((failure) => {
        if (alive) {
          setError(failure instanceof Error ? failure.message : '예약 내역을 가져오지 못했습니다.')
        }
      })

    return () => {
      alive = false
    }
  }, [userId, reloadKey])

  const now = new Date()
  const upcoming = (items ?? []).filter((item) => visitAt(item) > now && item.status === 'BOOKED')
  const past = (items ?? []).filter((item) => !upcoming.includes(item)).reverse()

  return (
    <section className="hero-card reservation-page" aria-labelledby="reservation-title">
      <header className="reservation-head">
        <div>
          <h2 id="reservation-title">{userName} 님의 방문 예약</h2>
          <p>상담에서 가까운 지점을 찾고 &quot;예약하러 가기&quot;로 예약할 수 있어요.</p>
        </div>
        <button type="button" onClick={() => setReloadKey((key) => key + 1)} disabled={items === null && !error}>
          새로고침
        </button>
      </header>

      {error ? (
        <p className="reserve-error" role="alert">
          {error}
        </p>
      ) : null}

      {items === null && !error ? <p className="reservation-empty">예약 내역을 불러오는 중…</p> : null}

      {items !== null && items.length === 0 ? (
        <div className="reservation-empty">
          <p>아직 예약 내역이 없습니다.</p>
          <button type="button" onClick={onStartChat}>
            상담에서 가까운 지점 찾기
          </button>
        </div>
      ) : null}

      {[...upcoming, ...past].length > 0 ? (
        <ul className="reservation-list">
          {[...upcoming, ...past].map((item) => {
            const isPast = !upcoming.includes(item)

            return (
              <li key={item.reservation_id} className={isPast ? 'past' : undefined}>
                <div>
                  <strong>{item.store_name}</strong>
                  <span>{formatVisit(item)}</span>
                  <small>{item.store_address || '주소 정보 없음'}</small>
                </div>
                <div className="reservation-side">
                  <span className={`reservation-status ${isPast ? 'muted' : ''}`}>{statusLabel(item, isPast)}</span>
                  <small>예약 번호 {item.reservation_id}</small>
                  {isPast ? null : (
                    <button
                      type="button"
                      className="reservation-cancel"
                      onClick={() => void onCancel(item)}
                      disabled={cancelling !== null}
                    >
                      {cancelling === item.reservation_id ? '취소 중…' : '예약 취소'}
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}
