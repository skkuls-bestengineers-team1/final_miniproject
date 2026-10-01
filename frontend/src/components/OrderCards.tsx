import { useState } from 'react'
import type { ChatOrderCard } from '../api'

type OrderCardsProps = {
  orders: ChatOrderCard[]
}

function statusClass(status: string) {
  return `status-pill status-${status || 'UNKNOWN'}`
}

export function OrderCards({ orders }: OrderCardsProps) {
  const [open, setOpen] = useState<ChatOrderCard | null>(null)

  return (
    <>
      <div className="order-list">
        {orders.map((item) => (
          <article key={item.order_id} className="order-card">
            <img src={item.photo_url} alt={item.product_name} />
            <div>
              <span className={statusClass(item.delivery_status)}>
                {item.delivery_status_label || '상태 확인'}
              </span>
              <strong>{item.product_name}</strong>
              <p>{item.order_id}{item.option ? ` · ${item.option}` : ''}</p>
              <p>
                {item.order_date ? `${item.order_date} 주문` : ''}
                {item.expected_date ? ` · 예정 ${item.expected_date}` : ''}
              </p>
              <button type="button" onClick={() => setOpen(item)}>
                주문상세 보기
              </button>
            </div>
          </article>
        ))}
      </div>
      {open ? (
        <div className="modal-back" role="presentation" onClick={() => setOpen(null)}>
          <div
            className="modal"
            role="dialog"
            aria-labelledby="order-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2 id="order-title">{open.product_name}</h2>
              <button type="button" className="icon-btn" onClick={() => setOpen(null)} aria-label="닫기">
                ×
              </button>
            </header>
            <img className="modal-photo" src={open.photo_url} alt={open.product_name} />
            <p className="modal-meta">
              <span className={statusClass(open.delivery_status)}>
                {open.delivery_status_label}
              </span>
              <span>주문번호 {open.order_id}</span>
              {open.option ? <span>옵션 {open.option}</span> : null}
              {open.order_date ? <span>주문일 {open.order_date}</span> : null}
              {open.expected_date ? <span>예상 배송 {open.expected_date}</span> : null}
              {open.delivered_date ? <span>배송 완료 {open.delivered_date}</span> : null}
              {open.ship_address ? <span>배송지 {open.ship_address}</span> : null}
              {open.price != null ? <span>{open.price.toLocaleString('ko-KR')}원</span> : null}
            </p>
          </div>
        </div>
      ) : null}
    </>
  )
}
