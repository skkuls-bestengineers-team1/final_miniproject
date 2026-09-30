import { FormEvent, useState } from 'react'
import type { ChatStoreCard } from '../api'

type ReservationModalProps = {
  store: ChatStoreCard
  onClose: () => void
}

const SLOTS = ['10:00', '11:00', '14:00', '15:00', '16:00']

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export function ReservationModal({ store, onClose }: ReservationModalProps) {
  const [date, setDate] = useState(todayIso())
  const [time, setTime] = useState(SLOTS[0])
  const [done, setDone] = useState(false)
  const mapSrc =
    store.lat != null && store.lng != null
      ? `https://www.openstreetmap.org/export/embed.html?bbox=${store.lng - 0.01}%2C${store.lat - 0.01}%2C${store.lng + 0.01}%2C${store.lat + 0.01}&layer=mapnik&marker=${store.lat}%2C${store.lng}`
      : ''

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setDone(true)
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
        {done ? (
          <p className="notice">
            {date} {time} · {store.store_name} 방문 예약이 접수되었습니다. (데모)
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
            <button type="submit">예약 접수</button>
          </form>
        )}
      </div>
    </div>
  )
}
