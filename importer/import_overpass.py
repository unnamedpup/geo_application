import os
import json
import time
import requests
import psycopg

DB_URL = os.environ.get("DATABASE_URL", "postgresql://geo:geo@db:5432/geo")

CITY_QUERY = os.environ.get("CITY_QUERY", "Saint Petersburg, Russia")
OVERPASS_URLS = [u.strip() for u in os.environ.get(
    "OVERPASS_URLS",
    "https://overpass-api.de/api/interpreter"
).split(",") if u.strip()]

TILE_N = int(os.environ.get("TILE_N", "3"))


AMENITY = [
    "cafe","restaurant","fast_food","bar",
    "pharmacy","hospital","clinic",
    "school","university","kindergarten",
    "bank","atm","post_office",
    "fuel","police","fire_station",
]
SHOP = ["supermarket","convenience","bakery","clothes","mall"]

HEADERS = {
    "User-Agent": "GeoApp-SPB/1.0 (learning project; contact: none)",
    "Accept": "*/*",
}

def nominatim_city(city_query: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "jsonv2",
        "q": city_query,
        "limit": 1,
        "polygon_geojson": 1,
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise RuntimeError(f"Nominatim: city not found for query: {city_query}")

    item = data[0]
    # bbox: south, north, west, east (strings)
    south, north, west, east = map(float, item["boundingbox"])
    geojson = item.get("geojson")
    name = item.get("display_name", city_query)
    return name, (south, west, north, east), geojson

def _overpass_query_for_bbox(south, west, north, east):
    amenity_re = "|".join(AMENITY)
    shop_re = "|".join(SHOP)

    # timeout можно увеличить, но лучше дробить bbox
    return f"""
    [out:json][timeout:180];
    (
      node["amenity"~"^({amenity_re})$"]({south},{west},{north},{east});
      node["shop"~"^({shop_re})$"]({south},{west},{north},{east});
    );
    out body;
    """

def _post_overpass(query: str):
    last_err = None
    for url in OVERPASS_URLS:
        for attempt in range(1, 5):
            try:
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=220)
                if r.status_code in (429, 502, 503, 504):
                    wait = min(60, 2 ** attempt)
                    print(f"Overpass {url} -> {r.status_code}, retry in {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                wait = min(60, 2 ** attempt)
                print(f"Overpass error on {url}: {e}. retry in {wait}s")
                time.sleep(wait)
                continue
        print(f"Switching overpass server after failures: {url}")
    raise RuntimeError(f"All Overpass servers failed. Last error: {last_err}")

def _split_bbox(bbox, n: int):
    south, west, north, east = bbox
    lat_step = (north - south) / n
    lon_step = (east - west) / n
    tiles = []
    for i in range(n):
        for j in range(n):
            s = south + i * lat_step
            n_ = south + (i + 1) * lat_step
            w = west + j * lon_step
            e = west + (j + 1) * lon_step
            tiles.append((s, w, n_, e))
    return tiles

def overpass_pois(bbox):
    tiles = _split_bbox(bbox, TILE_N)
    print(f"Using tiling: {TILE_N}x{TILE_N} => {len(tiles)} requests")

    seen = set()
    out = []

    for idx, (s, w, n, e) in enumerate(tiles, start=1):
        print(f"Tile {idx}/{len(tiles)}: ({s},{w},{n},{e})")
        q = _overpass_query_for_bbox(s, w, n, e)
        js = _post_overpass(q)
        elems = js.get("elements", [])

        for el in elems:
            key = (el.get("type"), el.get("id"))
            if key in seen:
                continue
            seen.add(key)
            out.append(el)

        time.sleep(1)

    return out

def addr_from_tags(tags: dict) -> str | None:
    full = tags.get("addr:full")
    if full:
        return full
    street = tags.get("addr:street")
    house = tags.get("addr:housenumber")
    if street or house:
        return ", ".join([x for x in [street, house] if x])
    return None

def main():
    print("==> Nominatim: resolve city bbox & boundary")
    city_name, bbox, boundary_geojson = nominatim_city(CITY_QUERY)
    print(f"City: {city_name}")
    print(f"BBOX: {bbox}")

    print("==> Overpass: download POIs")
    elements = overpass_pois(bbox)
    print(f"Downloaded elements: {len(elements)}")

    print("==> Insert into PostGIS (truncate + insert)")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS hstore;")

            cur.execute("TRUNCATE places RESTART IDENTITY;")
            cur.execute("TRUNCATE districts RESTART IDENTITY;")

            if boundary_geojson:
                cur.execute(
                    """
                    INSERT INTO districts(name, admin_level, geom)
                    VALUES (
                      %s,
                      %s,
                      ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))::geometry(MultiPolygon,4326)
                    );
                    """,
                    ("Saint Petersburg", "city", json.dumps(boundary_geojson)),
                )
                print("Inserted district polygon from Nominatim.")
            else:
                print("No boundary_geojson from Nominatim (skip districts).")

            insert_sql = """
              INSERT INTO places(name, category, address, geom)
              VALUES (
                %s, %s, %s,
                ST_SetSRID(ST_MakePoint(%s,%s),4326)
              );
            """

            n = 0
            for el in elements:
                if el.get("type") != "node":
                    continue
                tags = el.get("tags") or {}
                lon = el.get("lon")
                lat = el.get("lat")
                if lon is None or lat is None:
                    continue

                category = tags.get("amenity") or tags.get("shop")
                if not category:
                    continue

                name = tags.get("name") or category
                address = addr_from_tags(tags)

                cur.execute(insert_sql, (name, category, address, float(lon), float(lat)))
                n += 1

            print(f"Inserted places: {n}")

        conn.commit()

    print("==> Done.")

if __name__ == "__main__":
    main()

