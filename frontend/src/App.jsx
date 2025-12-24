import React, { useEffect, useMemo, useState } from "react";
import { getJSON } from "./api";
import MapView from "./MapView.jsx";

export default function App() {
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("");
  const [radius, setRadius] = useState(800);
  const [showDistricts, setShowDistricts] = useState(true);

  useEffect(() => {
    getJSON("/api/categories").then(setCategories).catch(() => setCategories([]));
  }, []);

  const filters = useMemo(
    () => ({ category: category || null, radius, showDistricts }),
    [category, radius, showDistricts]
  );

  return (
    <div className="layout">
      <div className="sidebar">
        <h2>GeoApp (СПб)</h2>

        <div className="block">
          <label>Категория</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">(все)</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className="block">
          <label>Радиус поиска рядом: {radius} м</label>
          <input
            type="range"
            min="50"
            max="5000"
            step="50"
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          />
          <div className="hint">Клик по карте → поиск ближайших в радиусе.</div>
        </div>

        <div className="block">
          <label className="row">
            <input
              type="checkbox"
              checked={showDistricts}
              onChange={(e) => setShowDistricts(e.target.checked)}
            />
            <span>Показывать границы</span>
          </label>
        </div>

        <div className="footer">
          Backend: <a href="http://localhost:8000/api/health" target="_blank">health</a>
        </div>
      </div>

      <div className="map">
        <MapView filters={filters} />
      </div>
    </div>
  );
}
