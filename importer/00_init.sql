CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS hstore;

CREATE SCHEMA IF NOT EXISTS osm;

CREATE TABLE IF NOT EXISTS districts (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  admin_level TEXT,
  geom geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS districts_geom_gix ON districts USING GIST (geom);

CREATE TABLE IF NOT EXISTS places (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  address TEXT,
  geom geometry(Point, 4326) NOT NULL,
  geog geography(Point, 4326) GENERATED ALWAYS AS (geom::geography) STORED,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS places_geom_gix ON places USING GIST (geom);
CREATE INDEX IF NOT EXISTS places_geog_gix ON places USING GIST (geog);
CREATE INDEX IF NOT EXISTS places_category_idx ON places(category);
