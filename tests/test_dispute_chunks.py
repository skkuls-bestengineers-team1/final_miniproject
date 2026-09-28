'''분쟁해결기준 조 단위 적재.'''

from app.db.dispute_chunks import article_doc_id, group_articles


def test_article_doc_id():
    assert article_doc_id('제8조 청약철회 기간 및 제한에 관한 분쟁해결기준') == 'ART-08'
    assert article_doc_id('제1조 목적') == 'ART-01'


def test_group_articles_keeps_source_ids():
    rows = [
        {'doc_id': 'DOC-039', 'title': '제9조 반환비용', 'category': '제2장', 'content': '반환배송비는 소비자가 부담한다.'},
        {'doc_id': 'DOC-041', 'title': '제9조 반환비용', 'category': '제2장', 'content': '다음 각 호는 판매자가 부담한다.'},
        {'doc_id': 'DOC-045', 'title': '제9조 반환비용', 'category': '제2장', 'content': '하자 있는 재화가 배송된 경우'},
        {'doc_id': 'DOC-001', 'title': '제1조 목적', 'category': '제1장', 'content': '기준을 정한다.'},
    ]
    articles = group_articles(rows)

    assert [item['doc_id'] for item in articles] == ['ART-09', 'ART-01']
    ninth = articles[0]
    assert ninth['doc_ids'] == ['DOC-039', 'DOC-041', 'DOC-045']
    assert '판매자가 부담한다' in ninth['content']
    assert '하자 있는 재화' in ninth['content']
