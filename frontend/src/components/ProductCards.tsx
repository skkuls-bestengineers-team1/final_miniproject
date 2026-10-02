import { useState } from 'react'
import { createPortal } from 'react-dom'
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
            <div className="product-body">
              <strong>{item.product_name}</strong>
              <p className="product-meta">{item.category} · {item.store_name}</p>
              <div className="product-foot">
                <div className="product-facts">
                  <span className="product-stock">재고 {item.quantity}개</span>
                  {item.price != null ? (
                    <span className="product-price">{item.price.toLocaleString('ko-KR')}원</span>
                  ) : null}
                </div>
                <button type="button" onClick={() => setOpen(item)}>
                  상품정보 보기
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
      {open
        ? createPortal(
            <div className="modal-back product-modal-back" role="presentation" onClick={() => setOpen(null)}>
              <div
                className="modal product-modal"
                role="dialog"
                aria-labelledby="product-title"
                onClick={(event) => event.stopPropagation()}
              >
                <header>
                  <h2 id="product-title">{open.product_name}</h2>
                  <button type="button" className="icon-btn" onClick={() => setOpen(null)} aria-label="닫기">
                    ×
                  </button>
                </header>
                <img className="product-modal-photo" src={open.photo_url} alt={open.product_name} />
                {open.price != null ? (
                  <p className="product-modal-price">{open.price.toLocaleString('ko-KR')}원</p>
                ) : null}
                <dl className="product-specs">
                  <div>
                    <dt>모델</dt>
                    <dd>{open.product_code}</dd>
                  </div>
                  <div>
                    <dt>분류</dt>
                    <dd>{open.category}</dd>
                  </div>
                  <div>
                    <dt>지점</dt>
                    <dd>{open.store_name}</dd>
                  </div>
                  <div>
                    <dt>재고</dt>
                    <dd>{open.quantity}개</dd>
                  </div>
                </dl>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
