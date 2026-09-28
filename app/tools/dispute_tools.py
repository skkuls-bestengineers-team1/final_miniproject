'''분쟁해결기준 검색.

담당: 김동규
Postgres 테이블 dispute_docs + pgvector 코사인 유사도.
'''

from app.db.connection import fail, fetch_all
from app.db.embeddings import embed_texts


def search_dispute_docs(
        query: str,
        top_k: int = 5
) -> dict:
    '''질문과 가까운 조항을 거리 오름차순으로 반환한다.'''

    text = (query or '').strip()

    if not text:
        return fail('EMPTY_QUERY', '검색어가 없습니다.')

    vectors = embed_texts([text], task_type='RETRIEVAL_QUERY')

    if not vectors:
        return fail('EMBEDDING_UNAVAILABLE', '분쟁 기준 벡터를 만들지 못했습니다.')

    rows = fetch_all(
        '''
        SELECT
            doc_id,
            category,
            title,
            content,
            1 - (embedding <=> %s::vector) AS score
        FROM dispute_docs
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        ''',
        (vectors[0], vectors[0], top_k)
    )

    return {
        'ok': True,
        'items': rows,
    }
