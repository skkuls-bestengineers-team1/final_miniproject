import { FormEvent, useState } from 'react'
import { submitInquiry } from '../api'

type CustomerVoiceProps = {
  userId: string
  userName: string
}

export function CustomerVoice({ userId, userName }: CustomerVoiceProps) {
  const [inquiryType, setInquiryType] = useState('COMPLAINT')
  const [inquiryText, setInquiryText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submittedId, setSubmittedId] = useState<number | null>(null)
  const [error, setError] = useState('')

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const text = inquiryText.trim()

    if (!text) {
      setError('내용을 입력해 주세요.')
      return
    }

    setSubmitting(true)
    setError('')
    setSubmittedId(null)

    try {
      const result = await submitInquiry(
        userId,
        inquiryType,
        text,
      )

      setSubmittedId(result.inquiry_id)
      setInquiryText('')
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : '고객의 소리를 접수하지 못했습니다.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="hero-card customer-voice">
      <header>
        <h2>{userName} 님의 고객의 소리</h2>
        <p>서비스 이용 중 느낀 점이나 개선 의견을 남겨 주세요.</p>
      </header>

      <form onSubmit={onSubmit}>
        <label>
          문의 유형
          <select
            value={inquiryType}
            onChange={(event) => setInquiryType(event.target.value)}
          >
            <option value="COMPLAINT">불편 사항</option>
            <option value="SUGGESTION">개선 제안</option>
            <option value="PRAISE">칭찬</option>
            <option value="ETC">기타</option>
          </select>
        </label>

        <label>
          내용
          <textarea
            value={inquiryText}
            onChange={(event) => setInquiryText(event.target.value)}
            placeholder="내용을 입력해 주세요."
            rows={8}
          />
        </label>

        {error ? (
          <p className="reserve-error" role="alert">
            {error}
          </p>
        ) : null}

        {submittedId !== null ? (
          <p>
            고객의 소리가 정상적으로 접수되었습니다. 접수 번호는 {submittedId}번입니다.
          </p>
        ) : null}

        <button type="submit" disabled={submitting}>
          {submitting ? '접수 중…' : '접수하기'}
        </button>
      </form>
    </section>
  )
}