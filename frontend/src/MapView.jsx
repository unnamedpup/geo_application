import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  GeoJSON,
  Circle,
  useMapEvents
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { bboxToQuery, getJSON } from "./api";

// фикс иконок Leaflet в Vite/Docker
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png"
});

/**
 * Click / DoubleClick handler с защитой:
 * Leaflet обычно генерирует click вместе с dblclick, поэтому мы игнорируем click после dblclick.
 */
function ClickHandler({ onClick }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng);
    }
  });
  return null;
}

/**
 * События карты (bbox-режим). Объявлен снаружи MapView, чтобы не ремоунтился постоянно.
 * Есть дебаунс.
 */
function MapEvents({ category, onNeedReload, enabled }) {
  const timerRef = useRef(null);

  const map = useMapEvents(
    enabled
      ? {
          moveend: () => {
            clearTimeout(timerRef.current);
            timerRef.current = setTimeout(() => onNeedReload(map), 250);
          },
          zoomend: () => {
            clearTimeout(timerRef.current);
            timerRef.current = setTimeout(() => onNeedReload(map), 250);
          }
        }
      : {}
  );

  useEffect(() => {
    if (!enabled) return;
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onNeedReload(map), 0);
    return () => clearTimeout(timerRef.current);
  }, [category, enabled, map, onNeedReload]);

  return null;
}

export default function MapView({ filters }) {
  const center = useMemo(() => [59.9386, 30.3141], []);

  const mapRef = useRef(null);

  const [places, setPlaces] = useState(null);     // bbox results
  const [near, setNear] = useState(null);         // near results
  const [districts, setDistricts] = useState(null);

  const [clickPoint, setClickPoint] = useState(null); // {lat,lng} либо null

  const requestIdRef = useRef(0);

  // districts
  useEffect(() => {
    if (!filters.showDistricts) return;
    getJSON("/api/districts").then(setDistricts).catch(() => setDistricts(null));
  }, [filters.showDistricts]);

  const loadPlacesForMap = useCallback(async (map) => {
    if (!map) return;

    const id = ++requestIdRef.current;

    const b = map.getBounds();
    const bbox = {
      minLon: b.getWest(),
      minLat: b.getSouth(),
      maxLon: b.getEast(),
      maxLat: b.getNorth()
    };

    const qs = bboxToQuery(bbox);
    const cat = filters.category ? `&category=${encodeURIComponent(filters.category)}` : "";
    const fc = await getJSON(`/api/places?${qs}${cat}&limit=1500`);

    // защита от гонок: принимаем только последний ответ
    if (id === requestIdRef.current) {
      setPlaces(fc);
    }
  }, [filters.category]);

  const loadNear = useCallback(async (pt) => {
    if (!pt) return;

const cat = filters.category ? `&category=${encodeURIComponent(filters.category)}` : "";
    const fc = await getJSON(
      `/api/places/near?lon=${pt.lng}&lat=${pt.lat}&radius_m=${filters.radius}&limit=200${cat}`
    );
    setNear(fc);
  }, [filters.category, filters.radius]);

  // клик по карте -> near mode
  const onMapClick = useCallback(async (latlng) => {
    setClickPoint(latlng);
    await loadNear(latlng);
  }, [loadNear]);

  // сброс near mode -> bbox mode
  const onReset = useCallback(async () => {
    setClickPoint(null);
    setNear(null);

    // после сброса принудительно загрузим bbox-точки (чтобы не ждать move/zoom)
    if (mapRef.current) {
      await loadPlacesForMap(mapRef.current);
    }
  }, [loadPlacesForMap]);

  // 1) Если мы в near-режиме и поменяли радиус — перезагружаем near
  // 3) Если мы в near-режиме и поменяли категорию — тоже перезагружаем near
  useEffect(() => {
    if (!clickPoint) return;
    loadNear(clickPoint);
  }, [clickPoint, filters.radius, filters.category, loadNear]);

const featuresToShow =
    clickPoint && near?.features
      ? near.features
      : places?.features
      ? places.features
      : [];

  const bboxModeEnabled = clickPoint === null;

  return (
    <div className="mapwrap">
      {clickPoint && (
        <div className="map-controls">
          <button className="btn" onClick={onReset}>
            Сбросить поиск рядом
          </button>
        </div>
      )}

      <MapContainer
        center={center}
        zoom={11}
        style={{ height: "100%", width: "100%" }}
        whenCreated={(map) => {
          mapRef.current = map;
        }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapEvents
          enabled={bboxModeEnabled}
          category={filters.category}
          onNeedReload={loadPlacesForMap}
        />

        <ClickHandler onClick={onMapClick} />

        {filters.showDistricts && districts && (
          <GeoJSON
            data={districts}
            style={() => ({ color: "#2b6cb0", weight: 1, fillOpacity: 0.05 })}
          />
        )}

        {clickPoint && (
          <Circle
            center={clickPoint}
            radius={filters.radius}
            pathOptions={{ color: "#e53e3e", weight: 2, fillOpacity: 0.08 }}
          />
        )}

        {featuresToShow.map((f) => {
          const [lon, lat] = f.geometry.coordinates;
          const p = f.properties;
          return (
            <Marker key={`${p.id}`} position={[lat, lon]}>
              <Popup>
                <div style={{ fontWeight: 600 }}>{p.name}</div>
                <div>category: {p.category}</div>
                {p.address && <div>address: {p.address}</div>}
                {p.distance_m != null && <div>distance: {p.distance_m} m</div>}
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );

}
