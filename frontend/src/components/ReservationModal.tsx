import { FormEvent, useState } from 'react'
import { createReservation } from '../api'
import type { ChatStoreCard, Reservation } from '../api'

type ReservationModalProps = {
  userId: string
  store: ChatStoreCard
  onClose: () => void
}

// 서버 reservation_tools.RESERVATION_SLOTS와 같아야 한다.
const SLOTS = ['10:00', '11:00', '14:00', '15:00', '16:00']

// 로컬 날짜(YYYY-MM-DD). toISOString()은 UTC라 한국 오전 9시 전에는 하루 전 날짜가 된다.
function todayIso() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60 * 1000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function ReservationModal({ userId, store, onClose }: ReservationModalProps) {
  const [date, setDate] = useState(todayIso())
  const [time, setTime] = useState(SLOTS[0])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [reservation, setReservation] = useState<Reservation | null>(null)
  const mapSrc =
    store.lat != null && store.lng != null
      ? `https://www.openstreetmap.org/export/embed.html?bbox=${store.lng - 0.01}%2C${store.lat - 0.01}%2C${store.lng + 0.01}%2C${store.lat + 0.01}&layer=mapnik&marker=${store.lat}%2C${store.lng}`
      : ''

  async function onSubmit(event: FormEvent) {
    event.preventDefault()

    if (saving) {
      return
    }

    setSaving(true)
    setError('')

    try {
      setReservation(await createReservation(userId, store.store_name, date, time))
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '예약을 접수하지 못했습니다.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-back" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-labelledby="reserve-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2 id="reserve-title">방문 예약</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="닫기">
            ×
          </button>
        </header>
        <img className="modal-photo" src={store.photo_url} alt={`${store.store_name} 매장`} />
        {mapSrc ? (
          <iframe title={`${store.store_name} 위치`} className="modal-map" src={mapSrc} />
        ) : null}
        <p className="modal-meta">
          <strong>{store.store_name}</strong>
          <span>{store.address || '주소 정보 없음'}</span>
          {store.distance_km != null ? <span>현재 위치에서 약 {store.distance_km.toFixed(1)}km</span> : null}
        </p>
        {reservation ? (
          <p className="notice">
            예약 번호 {reservation.reservation_id} · {reservation.visit_date} {reservation.visit_time} ·{' '}
            {reservation.store_name} 방문 예약이 접수되었습니다.
          </p>
        ) : (
          <form className="reserve-form" onSubmit={onSubmit}>
            <label>
              날짜
              <input type="date" min={todayIso()} value={date} onChange={(event) => setDate(event.target.value)} required />
            </label>
            <label>
              시간
              <select value={time} onChange={(event) => setTime(event.target.value)}>
                {SLOTS.map((slot) => (
                  <option key={slot} value={slot}>
                    {slot}
                  </option>
                ))}
              </select>
            </label>
            <label>
              지점
              <input value={store.store_name} readOnly />
            </label>
            {error ? (
              <p className="reserve-error" role="alert">
                {error}
              </p>
            ) : null}
            <button type="submit" disabled={saving}>
              {saving ? '접수 중…' : '예약 접수'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
