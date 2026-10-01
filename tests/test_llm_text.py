'''Gemini 응답 블록에서 본문만 꺼낸다.'''

from types import SimpleNamespace

from app.llm import content_text, llm_text


def test_list_block_drops_signature():
    content = [{
        'type': 'text',
        'text': '반환 배송비는 판매자가 부담합니다.',
        'extras': {'signature': 'EpoVCpcVAWkUfRNibXK'},
    }]

    assert content_text(content) == '반환 배송비는 판매자가 부담합니다.'
    assert 'signature' not in content_text(content)
    assert llm_text(SimpleNamespace(content=content)) == '반환 배송비는 판매자가 부담합니다.'
