'''지점 좌표 GEO.

담당: 박서영
키: stores:geo
'''

GEO_KEY = 'stores:geo'


def load_store_geo(
        conn,
        client
) -> int:
    '''stores 테이블을 GEOADD로 다시 적재하고 건수를 반환한다.'''

    rows = conn.execute(
        'SELECT name, lng, lat FROM stores'
    ).fetchall()

    client.delete(GEO_KEY)

    if not rows:
        return 0

    # GEOADD 순서: 경도, 위도, 멤버
    payload: list = []

    for row in rows:
        payload.extend([row['lng'], row['lat'], row['name']])

    client.geoadd(GEO_KEY, payload)

    return len(rows)


def search_nearest(
        client,
        lng: float,
        lat: float,
        count: int = 3,
        radius_km: float = 50
) -> list[dict]:
    '''가까운 지점을 거리 오름차순으로 반환한다.'''

    found = client.geosearch(
        GEO_KEY,
        longitude=lng,
        latitude=lat,
        radius=radius_km,
        unit='km',
        sort='ASC',
        count=count,
        withdist=True,
    )

    stores = []

    for item in found or []:
        name = item[0]
        distance = float(item[1])

        stores.append({
            'store_name': name,
            'distance_km': distance,
        })

    return stores
