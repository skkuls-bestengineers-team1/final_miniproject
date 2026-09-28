'''범위 밖 문의 저장.

담당: 김동규
'''

from app.db.connection import execute, fail, fetch_one


def save_inquiry(
        user_id: str,
        inquiry_text: str,
        inquiry_type_code: str | None = None,
        handled_by: str | None = None,
        product_code: str | None = None,
        priority_level: int | None = None
) -> dict:
    user = fetch_one(
        'SELECT user_id FROM users WHERE user_id = %s',
        (user_id,)
    )

    if user is None:
        return fail('USER_NOT_FOUND', '로그인 사용자를 찾지 못했습니다.')

    if product_code:
        product = fetch_one(
            'SELECT product_code FROM products WHERE product_code = %s',
            (product_code,)
        )

        if product is None:
            product_code = None

    inquiry_id = execute(
        '''
        INSERT INTO inquiries (
            user_id, product_code, inquiry_type_code, inquiry_text,
            handled_by, priority_level, answer_status_code
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'WAITING')
        RETURNING inquiry_id
        ''',
        (
            user_id,
            product_code,
            inquiry_type_code,
            inquiry_text,
            handled_by,
            priority_level,
        )
    )

    return {
        'ok': True,
        'inquiry_id': inquiry_id,
    }
