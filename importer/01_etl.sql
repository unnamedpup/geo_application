-- Чистим старые данные приложения (OSM-сырые таблицы остаются)
TRUNCATE places RESTART IDENTITY;
TRUNCATE districts RESTART IDENTITY;

-- 1) Places: точки (amenity) из OSM
-- planet_osm_point создаётся osm2pgsql.
-- Важно: при импорте -l way уже в SRID 4326.
INSERT INTO places (name, category, address, geom)
SELECT
  COALESCE(name, amenity, shop, 'place') AS name,
  COALESCE(amenity, shop) AS category,
  COALESCE(
    NULLIF(tags->'addr:full',''),
    concat_ws(', ',
      NULLIF(tags->'addr:street',''),
      NULLIF(tags->'addr:housenumber','')
    )
  ) AS address,
  way::geometry(Point,4326) AS geom
FROM osm.planet_osm_point
WHERE
  (
    amenity IN (
      'cafe','restaurant','fast_food','bar',
      'pharmacy','hospital','clinic',
      'school','university','kindergarten',
      'bank','atm','post_office',
      'fuel','police','fire_station'
    )
    OR shop IN ('supermarket','convenience','bakery','clothes','mall')
  )
  AND way IS NOT NULL;

-- 2) Districts: административные границы (полигоны)
-- В OSM для СПб можно встретить разные admin_level. Берём несколько уровней.
INSERT INTO districts (name, admin_level, geom)
SELECT
  name,
  admin_level,
  ST_Multi(ST_MakeValid(way))::geometry(MultiPolygon,4326) AS geom
FROM osm.planet_osm_polygon
WHERE
  boundary = 'administrative'
  AND name IS NOT NULL
  AND admin_level IN ('8','9','10','11')
  AND way IS NOT NULL;

-- Небольшое упрощение геометрии (уменьшает payload)
UPDATE districts
SET geom = ST_Multi(ST_SimplifyPreserveTopology(geom, 0.0002))::geometry(MultiPolygon,4326);

ANALYZE places;
ANALYZE districts;
