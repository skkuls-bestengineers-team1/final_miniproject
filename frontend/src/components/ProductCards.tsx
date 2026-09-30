import { useState } from 'react'
import type { ChatProductCard } from '../api'

type ProductCardsProps = {
  products: ChatProductCard[]
}

export function ProductCards({ products }: ProductCardsProps) {
  const [open, setOpen] = useState<ChatProductCard | null>(null)

  return (
    <>
      <div className="product-grid">
        {products.map((item) => (
          <article key={`${item.product_code}-${item.store_name}`} className="product-card">
            <img src={item.photo_url} alt={item.product_name} />
            <div>
              <strong>{item.product_name}</strong>
              <p>{item.category} · {item.store_name}</p>
              <p>재고 {item.quantity}개{item.price != null ? ` · ${item.price.toLocaleString('ko-KR')}원` : ''}</p>
              <button type="button" onClick={() => setOpen(item)}>
                상품정보 보기
              </button>
            </div>
          </article>
        ))}
      </div>
      {open ? (
        <div className="modal-back" role="presentation" onClick={() => setOpen(null)}>
          <div className="modal" role="dialog" aria-labelledby="product-title" onClick={(event) => event.stopPropagation()}>
            <header>
              <h2 id="product-title">{open.product_name}</h2>
              <button type="button" className="icon-btn" onClick={() => setOpen(null)} aria-label="닫기">
                ×
              </button>
            </header>
            <img className="modal-photo" src={open.photo_url} alt={open.product_name} />
            <p className="modal-meta">
              <span>모델 {open.product_code}</span>
              <span>{open.category}</span>
              <span>{open.store_name} 재고 {open.quantity}개</span>
              {open.price != null ? <span>{open.price.toLocaleString('ko-KR')}원</span> : null}
            </p>
          </div>
        </div>
      ) : null}
    </>
  )
}
