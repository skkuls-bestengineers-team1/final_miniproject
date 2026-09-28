'''분쟁해결기준 벡터 검색.'''

import pytest

from app.db.init_db import init_db
from app.tools.dispute_tools import search_dispute_docs


def test_dispute_table_seeded(postgres_env):
    counts = init_db()
    assert counts['dispute_docs'] >= 80


def test_dispute_vector_search(postgres_env):
    counts = init_db()

    if not counts.get('dispute_embeddings'):
        pytest.skip('임베딩 API 키가 없어 벡터 검색을 건너뜁니다.')

    result = search_dispute_docs('배송 완료 후 7일 안에 청약철회가 되나요?', top_k=3)

    assert result.get('ok')
    assert result['items']
    titles = ' '.join(item['title'] for item in result['items'])
    assert '청약철회' in titles or '배송' in titles
