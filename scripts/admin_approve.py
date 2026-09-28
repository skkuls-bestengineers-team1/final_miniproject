'''관리자 승인 CLI.

담당: 최민정

서버가 떠 있는 상태에서:
    python scripts/admin_approve.py
번호와 a(승인) 또는 r(거절)을 입력한다.
'''

import json
import sys
import urllib.error
import urllib.request

API_BASE = 'http://localhost:8000'


def _request(
        method: str,
        path: str
) -> dict | list:
    req = urllib.request.Request(
        API_BASE + path,
        method=method,
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))

    except urllib.error.URLError as exc:
        print(f'API에 연결하지 못했습니다. {exc}')
        sys.exit(1)


def _print_pending() -> list:
    rows = _request('GET', '/admin/requests?status=PENDING')

    if not rows:
        print('대기 중인 요청이 없습니다.')
        return []

    for index, row in enumerate(rows, start=1):
        address = row.get('new_address') or '-'
        print(
            f"{index}. #{row['request_id']} {row['request_type']} "
            f"user={row['user_id']} order={row['order_id']} address={address}"
        )

    return rows


def main() -> None:
    rows = _print_pending()

    if not rows:
        return

    raw = input('번호와 처리(a 승인 / r 거절), 예: 1 a > ').strip().split()

    if len(raw) != 2 or not raw[0].isdigit() or raw[1] not in {'a', 'r'}:
        print('입력 형식은 "1 a" 입니다.')
        return

    index = int(raw[0]) - 1

    if index < 0 or index >= len(rows):
        print('목록에 없는 번호입니다.')
        return

    request_id = rows[index]['request_id']
    action = 'approve' if raw[1] == 'a' else 'reject'
    result = _request('POST', f'/admin/requests/{request_id}/{action}')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
