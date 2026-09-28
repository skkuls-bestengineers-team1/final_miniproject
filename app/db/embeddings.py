'''Gemini 임베딩.

담당: 김동규
문서·질문 벡터는 768차원(gemini-embedding-001)이다.
'''

from app.config import settings

EMBED_DIM = 768
BATCH_SIZE = 20


def embed_texts(
        texts: list[str],
        task_type: str = 'RETRIEVAL_DOCUMENT'
) -> list[list[float]] | None:
    '''API 키가 없거나 호출이 실패하면 None.'''

    api_key = settings.gemini_api_key

    if not api_key or not texts:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        vectors: list[list[float]] = []

        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            response = client.models.embed_content(
                model=settings.embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBED_DIM,
                ),
            )
            vectors.extend(
                list(item.values)
                for item in response.embeddings
            )

        return vectors

    except Exception as exc:
        print(f'임베딩 생략: {exc}')
        return None
