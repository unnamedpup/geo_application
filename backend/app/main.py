import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from .db import pool

app = FastAPI(title="GeoApp (SPB)")

cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/categories")
def categories():
    sql = "SELECT DISTINCT category FROM places ORDER BY category;"
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return [r["category"] for r in cur.fetchall()]


@app.get("/api/districts")
def get_districts():
    sql = """
    SELECT jsonb_build_object(
      'type','FeatureCollection',
      'features', COALESCE(jsonb_agg(feature), '[]'::jsonb)
    )
    FROM (
      SELECT jsonb_build_object(
        'type','Feature',
        'geometry', ST_AsGeoJSON(geom)::jsonb,
        'properties', jsonb_build_object(
          'id', id,
          'name', name,
          'admin_level', admin_level
        )
      ) AS feature
      FROM districts
      ORDER BY name
    ) t;
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]


@app.get("/api/places")
def get_places(
    minLon: float = Query(...),
    minLat: float = Query(...),
    maxLon: float = Query(...),
    maxLat: float = Query(...),
    category: str | None = Query(None),
    limit: int = Query(3000, ge=1, le=10000),
):
    sql = """
    WITH env AS (
      SELECT ST_MakeEnvelope(%s,%s,%s,%s,4326) AS e
    )
    SELECT jsonb_build_object(
      'type','FeatureCollection',
      'features', COALESCE(jsonb_agg(feature), '[]'::jsonb)
    )
    FROM (
      SELECT jsonb_build_object(
        'type','Feature',
        'geometry', ST_AsGeoJSON(p.geom)::jsonb,
        'properties', jsonb_build_object(
          'id', p.id,
          'name', p.name,
          'category', p.category,
          'address', p.address
        )
      ) AS feature
      FROM places p, env
      WHERE p.geom && env.e
        AND ST_Intersects(p.geom, env.e)
        AND (%s::text IS NULL OR p.category = %s::text)
      LIMIT %s
    ) t;
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (minLon, minLat, maxLon, maxLat, category, category, limit))
            return cur.fetchone()[0]


@app.get("/api/places/near")
def near_places(
    lon: float,
    lat: float,
    radius_m: int = Query(800, ge=50, le=20000),
    category: str | None = Query(None),
    limit: int = Query(30, ge=1, le=200),
):
    sql = """
    WITH q AS (
      SELECT ST_SetSRID(ST_MakePoint(%s,%s),4326) AS pt
    )
    SELECT jsonb_build_object(
      'type','FeatureCollection',
      'features', COALESCE(jsonb_agg(feature), '[]'::jsonb)
    )
    FROM (
      SELECT jsonb_build_object(
        'type','Feature',
        'geometry', ST_AsGeoJSON(p.geom)::jsonb,
        'properties', jsonb_build_object(
          'id', p.id,
          'name', p.name,
          'category', p.category,
          'address', p.address,
          'distance_m', round(ST_Distance(p.geog, q.pt::geography)::numeric, 1)
        )
      ) AS feature
      FROM places p, q
      WHERE ST_DWithin(p.geog, q.pt::geography, %s)
        AND (%s::text IS NULL OR p.category = %s::text)
      ORDER BY ST_Distance(p.geog, q.pt::geography)
      LIMIT %s
    ) t;
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (lon, lat, radius_m, category, category, limit))
            return cur.fetchone()[0]
