import { useState } from 'react'
import { QUICK_PROMPTS } from './ChatWindow'

type FaqItem = {
  question: string
  answer: string
  prompt: string
}

const FAQS: FaqItem[] = [
  {
    question: '주문 내역은 어디서 확인하나요?',
    answer:
      '사성 CS Bot에 “주문 내역 보여주세요”라고 물어보시면 최근 주문을 카드로 보여 드립니다. 각 카드의 주문상세 보기에서 배송지·결제금액·상태를 확인할 수 있습니다.',
    prompt: QUICK_PROMPTS[2],
  },
  {
    question: '배송지를 변경할 수 있나요?',
    answer:
      '출고 전 주문은 배송지 변경을 접수할 수 있습니다. 변경은 관리자 승인 후 반영되며, 이미 출고·배송 중인 주문은 변경이 제한될 수 있습니다.',
    prompt: QUICK_PROMPTS[4],
  },
  {
    question: '교환은 언제까지 신청할 수 있나요?',
    answer:
      '배송 완료일부터 7일 이내에 교환을 신청할 수 있습니다. 기간이 지났거나 사용으로 상품 가치가 크게 줄어든 경우에는 접수가 어려울 수 있습니다.',
    prompt: QUICK_PROMPTS[5],
  },
  {
    question: '색상이 다른 제품을 받았어요. 반품 배송비는 누가 내나요?',
    answer:
      '표시·광고와 다른 상품이 배송된 경우 반환 배송비는 판매자가 부담합니다. 단순 변심 반품은 고객 부담이 원칙입니다. 상담에서 해당 주문을 확인한 뒤 안내해 드립니다.',
    prompt: QUICK_PROMPTS[6],
  },
  {
    question: '가까운 서비스 센터는 어떻게 찾나요?',
    answer:
      '현재 위치나 역·동 이름을 알려 주시면 가까운 지점을 거리 순으로 보여 드립니다. 지점 카드에서 예약하러 가기로 방문 일정을 잡을 수 있습니다.',
    prompt: QUICK_PROMPTS[0],
  },
]

type FaqListProps = {
  onAsk: (prompt: string) => void
}

export function FaqList({ onAsk }: FaqListProps) {
  const [open, setOpen] = useState(0)

  return (
    <section className="hero-card faq-page" aria-labelledby="faq-title">
      <header className="reservation-head">
        <div>
          <p>배송·교환·반품·센터 찾기를 먼저 확인해 보세요. 더 자세한 내용은 상담으로 이어집니다.</p>
        </div>
      </header>

      <ul className="faq-list">
        {FAQS.map((item, index) => {
          const expanded = open === index

          return (
            <li key={item.question} className={expanded ? 'open' : undefined}>
              <button
                type="button"
                className="faq-q"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? -1 : index)}
              >
                <span>Q</span>
                {item.question}
              </button>
              {expanded ? (
                <div className="faq-a">
                  <p>{item.answer}</p>
                  <button type="button" onClick={() => onAsk(item.prompt)}>
                    상담에서 이어서 물어보기
                  </button>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
