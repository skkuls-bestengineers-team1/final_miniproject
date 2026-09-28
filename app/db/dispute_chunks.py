'''분쟁해결기준 CSV를 조(title) 단위로 묶는다.

담당: 김동규
'''

import re
from collections import OrderedDict

ARTICLE_RE = re.compile(r'제\s*(\d+)\s*조')


def _strip(
        text: str
) -> str:
    return (text or '').strip()


def article_doc_id(
        title: str
) -> str:
    '''title의 제N조에서 ART-NN을 만든다.'''

    matched = ARTICLE_RE.search(title or '')

    if not matched:
        raise ValueError(f'조 번호를 찾지 못했습니다: {title}')

    return f'ART-{int(matched.group(1)):02d}'


def group_articles(
        rows: list[dict]
) -> list[dict]:
    '''CSV 순서를 유지한 채 title이 같은 행을 하나로 합친다.'''

    grouped: OrderedDict[str, dict] = OrderedDict()

    for row in rows:
        title = _strip(row.get('title', ''))
        category = _strip(row.get('category', ''))
        content = _strip(row.get('content', ''))
        source_id = _strip(row.get('doc_id', ''))

        if not title:
            continue

        if title not in grouped:
            grouped[title] = {
                'doc_id': article_doc_id(title),
                'category': category,
                'title': title,
                'doc_ids': [],
                'parts': [],
            }

        if source_id:
            grouped[title]['doc_ids'].append(source_id)

        if content:
            grouped[title]['parts'].append(content)

    articles = []

    for item in grouped.values():
        articles.append({
            'doc_id': item['doc_id'],
            'category': item['category'],
            'title': item['title'],
            'doc_ids': item['doc_ids'],
            'content': '\n'.join(item['parts']),
        })

    return articles
