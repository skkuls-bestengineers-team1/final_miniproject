'''지점 방문 예약 저장·취소와 검증.'''

from datetime import date, timedelta

from app.db.connection import execute
from app.db.init_db import init_db
from app.tools.reservation_tools import cancel_reservation, create_reservation, list_reservations

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def test_reservation_saved_and_listed(postgres_env):
    init_db()

    result = create_reservation('U001', '강남역점', TOMORROW, '14:00')

    assert result['ok']
    assert result['store_name'] == '강남역점'
    assert result['status'] == 'BOOKED'

    rows = list_reservations('U001')
    assert [(row['reservation_id'], row['visit_time']) for row in rows] == [(result['reservation_id'], '14:00')]
    assert list_reservations('U002') == []


def test_same_slot_twice_rejected(postgres_env):
    init_db()

    assert create_reservation('U001', '강남역점', TOMORROW, '10:00')['ok']
    second = create_reservation('U001', '용산점', TOMORROW, '10:00')

    assert not second['ok']
    assert second['error_code'] == 'DUPLICATE_SLOT'
    assert len(list_reservations('U001')) == 1

    # 다른 사용자는 같은 시간에 예약할 수 있다.
    assert create_reservation('U002', '강남역점', TOMORROW, '10:00')['ok']


def test_invalid_requests_rejected(postgres_env):
    init_db()

    cases = {
        'PAST_DATETIME': ('U001', '강남역점', YESTERDAY, '10:00'),
        'INVALID_SLOT': ('U001', '강남역점', TOMORROW, '12:00'),
        'INVALID_DATE': ('U001', '강남역점', '2026-13-40', '10:00'),
        'STORE_NOT_FOUND': ('U001', '없는점', TOMORROW, '10:00'),
        'USER_NOT_FOUND': ('U999', '강남역점', TOMORROW, '10:00'),
    }

    for error_code, args in cases.items():
        result = create_reservation(*args)
        assert not result['ok'], error_code
        assert result['error_code'] == error_code

    assert list_reservations('U001') == []


def test_cancel_frees_the_slot(postgres_env):
    init_db()

    booked = create_reservation('U001', '강남역점', TOMORROW, '11:00')
    cancelled = cancel_reservation('U001', booked['reservation_id'])

    assert cancelled['ok']
    assert cancelled['status'] == 'CANCELLED'
    assert cancelled['cancelled_at']

    # 행은 남고 상태만 바뀐다.
    rows = list_reservations('U001')
    assert [(row['reservation_id'], row['status']) for row in rows] == [(booked['reservation_id'], 'CANCELLED')]

    # 취소한 시간대는 다시 예약할 수 있다.
    assert create_reservation('U001', '용산점', TOMORROW, '11:00')['ok']


def test_cancel_rejected_cases(postgres_env):
    init_db()

    booked = create_reservation('U001', '강남역점', TOMORROW, '16:00')

    # 다른 사람의 예약은 없는 예약처럼 답한다.
    other = cancel_reservation('U002', booked['reservation_id'])
    assert other['error_code'] == 'RESERVATION_NOT_FOUND'
    assert cancel_reservation('U001', 999999)['error_code'] == 'RESERVATION_NOT_FOUND'

    assert cancel_reservation('U001', booked['reservation_id'])['ok']
    assert cancel_reservation('U001', booked['reservation_id'])['error_code'] == 'ALREADY_CANCELLED'

    # 지난 예약은 API로 만들 수 없어 직접 넣는다.
    past_id = execute(
        '''
        INSERT INTO reservations (user_id, store_id, visit_date, visit_time)
        VALUES ('U001', 'S001', %s, '10:00')
        RETURNING reservation_id
        ''',
        (YESTERDAY,)
    )
    assert cancel_reservation('U001', past_id)['error_code'] == 'PAST_RESERVATION'
