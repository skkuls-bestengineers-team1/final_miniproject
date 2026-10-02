from app.graph.confirm import looks_like_continuation, parse_yes_no
from app.graph.supervisor import classify_intent, classify_keyword, decide_target


'''문의 CSV 분류.

LLM 키가 없으면 실제 분류 테스트는 건너뛴다.
정답 매핑 자체는 키 없이 확인한다.
'''

import csv
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / 'data' / 'inquiries_testset.csv'

FALLBACK_CODES = {'PAYMENT', 'ACCOUNT', 'TECHNICAL', 'PRODUCT_QUALITY'}


def expected_target(
        inquiry_type_code: str,
        inquiry_text: str
) -> str | None:
    '''빈 본문은 테스트에서 제외한다. 정답은 본문 기준.'''

    text = (inquiry_text or '').strip()

    if not text:
        return None

    code = (inquiry_type_code or '').strip()

    if code == 'DELIVERY':
        return 'worker3'

    if not code and '배송지' in text:
        return 'worker3'

    if code in {'EXCHANGE', 'RETURN'}:
        return 'worker4'

    if code in FALLBACK_CODES:
        return 'fallback'

    return 'fallback'


def _rows() -> list[dict]:
    with CSV_PATH.open(encoding='utf-8') as file:
        return list(csv.DictReader(file))


def test_classify_keyword_out_of_scope():
    assert classify_keyword('결제가 두 번 됐어요') == 'fallback'
    assert classify_keyword('결제가 두 번 되었습니다') == 'fallback'
    assert classify_keyword('비밀번호를 잊어버렸습니다') == 'fallback'
    assert classify_keyword('색상이 달라 교환하고 싶습니다') == 'worker4'
    assert classify_keyword('주문 내역 보여주세요') == 'worker3'
    assert classify_keyword('주문조회할래') == 'worker3'
    assert classify_keyword('관련 규정이 어떻게 되는데?') == 'worker4'
    assert classify_keyword('청약철회 기간이 어떻게 되나요?') == 'worker4'
    assert classify_keyword('반환 비용 부담이 어떻게 되나요?') == 'worker4'
    assert classify_keyword('제9조 알려줘') == 'worker4'
    assert classify_keyword('반품 배송비는 누가 내나요?') == 'worker4'


def test_expected_mapping_rules():
    rows = _rows()
    checked = 0

    for row in rows:
        target = expected_target(
            row.get('inquiry_type_code', ''),
            row.get('inquiry_text', ''),
        )

        if target is None:
            assert not (row.get('inquiry_text') or '').strip()
            continue

        checked += 1

        if row['inquiry_type_code'] == 'DELIVERY' and '배송지를 변경' in row['inquiry_text']:
            assert target == 'worker3'

        if row['inquiry_type_code'] in {'EXCHANGE', 'RETURN'}:
            assert target == 'worker4'

        if row['inquiry_type_code'] in FALLBACK_CODES:
            assert target == 'fallback'

        if not row['inquiry_type_code'].strip() and '배송지' in row['inquiry_text']:
            assert target == 'worker3'

    assert checked >= 1
    assert sum(1 for row in rows if row['inquiry_id'] == 'WEB-00035') == 2


def test_llm_classification():
    '''TODO(나송주): LLM 분류 결과와 expected_target을 비교한다.'''

    if not os.getenv('GEMINI_API_KEY') and not os.getenv('GOOGLE_API_KEY'):
        pytest.skip('LLM 키가 없어 분류 테스트를 건너뜁니다.')

    rows = _rows()
    checked = 0

    for row in rows:
        expected = expected_target(
            row.get('inquiry_type_code', ''),
            row.get('inquiry_text', ''),
        )

        if expected is None:
            continue

        result = classify_intent(
            row['inquiry_text']
        )

        assert result.target == expected
        checked += 1

    assert checked >= 1


@pytest.mark.parametrize(
    'text, expected',
    [
        ('가까운 매장 알려줘', 'worker1'),
        ('로봇청소기를 사려고 합니다', 'worker1'),
        ('로봇청소기를 구매하려고요', 'worker1'),
        ('로봇청소기를 사려고 하는데 재고 있어요?', 'worker2'),
        ('강남역점에 로봇청소기 재고 있어?', 'worker2'),
        ('내 주문 배송 언제 와?', 'worker3'),
        ('구매한 제품 환불하고 싶어', 'worker4'),
        ('비밀번호 변경하고 싶어', 'fallback'),
        ('결제가 두 번 됐어요', 'fallback'),
        ('결제가 두 번 되었습니다', 'fallback'),
    ]
)
def test_basic_llm_routes(text, expected):

    if not os.getenv('GEMINI_API_KEY') and not os.getenv('GOOGLE_API_KEY'):
        pytest.skip('LLM 키가 없어 분류 테스트를 건너뜁니다.')

    result = decide_target(text)

    assert result == expected


def test_continuation_keywords_skip_llm():
    assert looks_like_continuation('confirm_order', '이거 맞아')
    assert looks_like_continuation('select_method', '지점 방문')
    assert looks_like_continuation('select_method', '택배 수거')
    assert looks_like_continuation('confirm_order', '관련 규정이 어떻게 되는데?')
    assert looks_like_continuation('confirm_order', '제9조의 정보를 알고 싶습니다')
    assert looks_like_continuation('confirm_order', '상품정보 보기가 왜 나와?')
    assert not looks_like_continuation('select_method', '가까운 매장 알려줘')
    assert parse_yes_no('이거 맞아') == 'yes'
    assert parse_yes_no('아니요') == 'no'
