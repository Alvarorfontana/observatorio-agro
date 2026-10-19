import { useEffect, useState } from "react";
import { FloodRadarPanel, type FloodRadarReport } from "./FloodRadarPanel";

type Props = { polygon: number[][]; lat: number; lon: number; location?: string };
export function FloodRadarConnected({ polygon, lat, lon, location }: Props) {
  const [report, setReport] = useState<FloodRadarReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const polygonKey = JSON.stringify(polygon);
  useEffect(() => {
    if (polygon.length < 3 || !Number.isFinite(lat) || !Number.isFinite(lon)) {
      setReport(null); setError("Dibujá un lote para analizarlo"); return;
    }
    const ctrl = new AbortController();
    setLoading(true); setReport(null); setError("");
    const query = new URLSearchParams({ lat: String(lat), lon: String(lon), polygon: polygonKey, days: "60" });
    fetch(`/api/fuentes/radar-cambio?${query}`, { signal: ctrl.signal })
      .then(async response => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "El servidor de radar no respondió");
        if (body.status === "sin dato") throw new Error(body.error || "No hay escenas suficientes");
        return body as FloodRadarReport;
      })
      .then(setReport)
      .catch(e => { if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : "No se pudo consultar el radar"); })
      .finally(() => { if (!ctrl.signal.aborted) setLoading(false); });
    return () => ctrl.abort();
  }, [polygonKey, lat, lon, refresh]);
  return <div>
    <FloodRadarPanel report={report} loading={loading} location={location} onRefresh={() => setRefresh(v => v + 1)} />
    {error && <p role="alert" style={{ color: "#c66b43", margin: "10px 0" }}>{error}</p>}
  </div>;
}
