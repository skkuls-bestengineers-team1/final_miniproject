import type { ChatUi } from '../api'
import { OrderCards } from './OrderCards'
import { ProductCards } from './ProductCards'

export type ChatMessage = {
  role: 'user' | 'bot'
  text: string
  time?: string
  ui?: ChatUi | null
}

type MessageBubbleProps = {
  message: ChatMessage
  onReserve?: (storeName: string) => void
}

export function MessageBubble({ message, onReserve }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="row user">
        <div className="bubble user">{message.text}</div>
        {message.time ? <time>{message.time}</time> : null}
      </div>
    )
  }

  const stores = message.ui?.stores || []
  const products = message.ui?.products || []
  const orders = message.ui?.orders || []

  return (
    <div className="row bot">
      <div className="bot-face" aria-hidden="true">✧</div>
      <div className="bot-stack">
        <div className="bubble bot">{message.text}</div>
        {stores.length ? (
          <div className="store-list">
            {stores.map((store) => (
              <article key={store.store_name} className="store-card">
                <img src={store.photo_url} alt={store.store_name} />
                <div>
                  <strong>
                    {store.rank}순위 {store.store_name}
                  </strong>
                  <p>{store.address}</p>
                  {store.distance_km != null ? <p>거리 약 {store.distance_km.toFixed(1)}km</p> : null}
                  <button type="button" onClick={() => onReserve?.(store.store_name)}>
                    예약하러 가기
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
        {products.length ? <ProductCards products={products} /> : null}
        {orders.length ? <OrderCards orders={orders} /> : null}
        {message.time ? <time>{message.time}</time> : null}
      </div>
    </div>
  )
}
