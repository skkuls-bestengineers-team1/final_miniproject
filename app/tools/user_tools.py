'''사용자 조회.

담당: 김동규
'''

from app.db.connection import fail, fetch_one


def get_user(
        user_id: str
) -> dict:
    '''사용자 정보. 없으면 USER_NOT_FOUND.'''

    row = fetch_one(
        '''
        SELECT user_id, name, phone, address, lat, lng
        FROM users
        WHERE user_id = %s
        ''',
        (user_id,)
    )

    if row is None:
        return fail('USER_NOT_FOUND', '로그인 사용자를 찾지 못했습니다.')

    return {
        'ok': True,
        **row,
    }


def get_user_address(
        user_id: str
) -> dict:
    '''주소와 좌표.'''

    user = get_user(user_id)

    if not user.get('ok'):
        return user

    return {
        'ok': True,
        'address': user['address'],
        'lat': user['lat'],
        'lng': user['lng'],
    }
