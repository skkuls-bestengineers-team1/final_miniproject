'''지점 방문 예약 저장과 검증.'''

from datetime import date, timedelta

from app.db.init_db import init_db
from app.tools.reservation_tools import create_reservation, list_reservations

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
