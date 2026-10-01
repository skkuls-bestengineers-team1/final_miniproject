'''지점 방문 예약.

담당: 박서영
예약 팝업(ReservationModal)의 "예약 접수"가 POST /reservations로 이 Tool을 부른다.
날짜·시간·지점·중복은 코드로 검증한다.
'''

from datetime import datetime

from psycopg.errors import UniqueViolation

from app.db.connection import execute, fail, fetch_all, fetch_one

RESERVATION_SLOTS = ('10:00', '11:00', '14:00', '15:00', '16:00')   # 프론트 SLOTS와 같아야 한다.


def _parse_visit(
        visit_date: str,
        visit_time: str
) -> datetime | None:
    try:
        return datetime.strptime(f'{visit_date} {visit_time}', '%Y-%m-%d %H:%M')

    except (TypeError, ValueError):
        return None


def _reservation_row(
        reservation_id: int
) -> dict | None:
    return fetch_one(
        '''
        SELECT r.reservation_id, r.user_id, r.store_id, s.name AS store_name, s.address AS store_address,
               r.visit_date, r.visit_time, r.status, r.created_at
        FROM reservations r
        JOIN stores s ON s.store_id = r.store_id
        WHERE r.reservation_id = %s
        ''',
        (reservation_id,)
    )


def create_reservation(
        user_id: str,
        store_name: str,
        visit_date: str,
        visit_time: str
) -> dict:
    '''방문 예약을 저장한다. 성공하면 예약 정보, 실패하면 fail().'''

    if visit_time not in RESERVATION_SLOTS:
        return fail('INVALID_SLOT', f"예약 가능한 시간은 {', '.join(RESERVATION_SLOTS)}입니다.")

    visit_at = _parse_visit(visit_date, visit_time)

    if visit_at is None:
        return fail('INVALID_DATE', '날짜는 YYYY-MM-DD 형식이어야 합니다.')

    if visit_at <= datetime.now():
        return fail('PAST_DATETIME', '지난 시간은 예약할 수 없습니다. 다른 날짜나 시간을 골라 주세요.')

    user = fetch_one('SELECT user_id FROM users WHERE user_id = %s', (user_id,))

    if user is None:
        return fail('USER_NOT_FOUND', '로그인 사용자를 찾지 못했습니다.')

    store = fetch_one('SELECT store_id FROM stores WHERE name = %s', (store_name,))

    if store is None:
        return fail('STORE_NOT_FOUND', f'{store_name} 지점을 찾지 못했습니다.')

    try:
        reservation_id = execute(
            '''
            INSERT INTO reservations (user_id, store_id, visit_date, visit_time)
            VALUES (%s, %s, %s, %s)
            RETURNING reservation_id
            ''',
            (user_id, store['store_id'], visit_date, visit_time)
        )

    except UniqueViolation:
        return fail('DUPLICATE_SLOT', f'{visit_date} {visit_time}에 이미 예약이 있습니다.')

    return {
        'ok': True,
        **_reservation_row(reservation_id),
    }


def list_reservations(
        user_id: str
) -> list[dict]:
    '''사용자의 예약 목록. 방문일·시간 순.'''

    return fetch_all(
        '''
        SELECT r.reservation_id, r.user_id, r.store_id, s.name AS store_name, s.address AS store_address,
               r.visit_date, r.visit_time, r.status, r.created_at
        FROM reservations r
        JOIN stores s ON s.store_id = r.store_id
        WHERE r.user_id = %s
        ORDER BY r.visit_date, r.visit_time, r.reservation_id
        ''',
        (user_id,)
    )
