'''화면 표시용 코드 한글명.

담당: 김동규
'''

DELIVERY_STATUS_LABEL = {
    'PREPARING': '입고 전',
    'SHIPPED': '출하 완료',
    'IN_TRANSIT': '배송 중',
    'DELIVERED': '배송 완료',
}

CATEGORY_LABEL = {
    'WEARABLE': '웨어러블',
    'AUDIO': '오디오',
    'TABLET': '태블릿',
    'POWER': '충전',
    'SMART_HOME': '스마트홈',
    'COMPUTER': '컴퓨터',
    'ROBOT_CLEANER': '로봇청소기',
}

REQUEST_TYPE_LABEL = {
    'ADDRESS_CHANGE': '배송지 변경',
    'EXCHANGE': '교환',
    'REFUND': '환불',
}

METHOD_LABEL = {
    'STORE_VISIT': '지점 방문',
    'PICKUP': '택배 수거',
}

INQUIRY_TYPE_LABEL = {
    'DELIVERY': '배송',
    'EXCHANGE': '교환',
    'RETURN': '반품·환불',
    'PAYMENT': '결제',
    'ACCOUNT': '계정',
    'TECHNICAL': '기술',
    'PRODUCT_QUALITY': '품질',
}

ANSWER_STATUS_LABEL = {
    'WAITING': '답변 대기',
    'IN_PROGRESS': '처리 중',
    'ANSWERED': '답변 완료',
}

# 제품명 전체가 발화에 없을 때 worker2가 쓰는 임시 키워드.
# TODO(박서영): LLM 추출로 교체
CATEGORY_KEYWORDS = {
    '로봇청소기': 'ROBOT_CLEANER',
    '워치': 'WEARABLE',
    '이어폰': 'AUDIO',
    '태블릿': 'TABLET',
    '충전기': 'POWER',
    '허브': 'SMART_HOME',
    '키보드': 'COMPUTER',
}


def format_korean_date(
        iso_date: str | None
) -> str:
    '''YYYY-MM-DD를 9월 28일 형식으로 바꾼다.'''

    if not iso_date:
        return ''

    parts = iso_date.split('-')

    if len(parts) != 3:
        return iso_date

    return f'{int(parts[1])}월 {int(parts[2])}일'
