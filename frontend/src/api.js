const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function getJSON(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

export function bboxToQuery(b) {
  // b: {minLon,minLat,maxLon,maxLat}
  const p = new URLSearchParams({
    minLon: b.minLon,
    minLat: b.minLat,
    maxLon: b.maxLon,
    maxLat: b.maxLat
  });
  return p.toString();
}
