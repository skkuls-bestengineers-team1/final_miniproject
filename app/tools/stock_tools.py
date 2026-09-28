'''재고 조회.

담당: 박서영
'''

from app.db.connection import fail, fetch_all, fetch_one


def _find_store(
        store_name: str
) -> dict | None:
    rows = fetch_all(
        '''
        SELECT store_id, name, address
        FROM stores
        WHERE name = %s OR name LIKE %s
        ''',
        (store_name, f'%{store_name}%')
    )

    exact = [row for row in rows if row['name'] == store_name]

    if len(exact) == 1:
        return exact[0]

    starts = [row for row in rows if row['name'].startswith(store_name)]

    if len(starts) == 1:
        return starts[0]

    if len(rows) == 1:
        return rows[0]

    return None


def get_stock(
        store_name: str,
        category_code: str | None = None,
        product_name: str | None = None
) -> dict:
    '''지점 재고. 제품명이 있으면 해당 제품만, 없으면 카테고리 목록과 합계.'''

    store = _find_store(store_name)

    if store is None:
        return fail('STORE_NOT_FOUND', f'{store_name} 지점을 찾지 못했습니다.')

    if product_name:
        product = fetch_one(
            '''
            SELECT product_code, product_name
            FROM products
            WHERE product_name = %s
            ''',
            (product_name,)
        )

        if product is None:
            return fail('PRODUCT_NOT_FOUND', f'{product_name} 제품을 찾지 못했습니다.')

    sql = '''
        SELECT p.product_code, p.product_name, p.category_code, i.quantity
        FROM inventory i
        JOIN products p ON p.product_code = i.product_code
        WHERE i.store_id = %s
    '''
    params: list = [store['store_id']]

    if product_name:
        sql += ' AND p.product_name = %s'
        params.append(product_name)

    elif category_code:
        sql += ' AND p.category_code = %s'
        params.append(category_code)

    sql += ' ORDER BY p.product_name'

    items = fetch_all(sql, tuple(params))
    total = sum(int(item['quantity']) for item in items)

    return {
        'ok': True,
        'store_name': store['name'],
        'items': items,
        'total': total,
        'product_name': product_name,
        'category_code': category_code,
    }
