import React, { useEffect, useState } from "react";

type VisionStatus = { status: string; missing_environment?: string[]; model?: string; identity_limit?: string };
type VisionResult = {
  status?: string; model?: string; device?: string; video_duration_seconds?: number;
  sampled_frames?: number; cattle_detections?: number; max_cattle_in_frame?: number;
  unique_temporary_track_ids?: number; limitations?: string[]; error?: string;
};

export function HerdVision() {
  const [file, setFile] = useState<File | null>(null);
  const [config, setConfig] = useState<VisionStatus | null>(null);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<VisionResult | null>(null);

  useEffect(() => {
    let live = true;
    fetch("/api/fuentes/vision/status").then(r => r.json()).then(j => { if (live) setConfig(j); })
      .catch(() => { if (live) setConfig({ status: "unavailable" }); });
    return () => { live = false; };
  }, []);

  async function analyze() {
    if (!file || working) return;
    if (file.size > 100 * 1024 * 1024) { setMessage("El video supera el máximo de 100 MB."); return; }
    if (!/\\.(mp4|mov|m4v)$/i.test(file.name)) { setMessage("Usá un video MP4, MOV o M4V."); return; }
    setWorking(true); setResult(null); setMessage("Solicitando carga privada…");
    try {
      const signed = await fetch("/api/fuentes/vision/upload-url", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, size: file.size }),
      });
      const upload = await signed.json();
      if (!signed.ok) throw new Error(upload.error || "No se pudo preparar la carga.");
      setMessage("Subiendo video al almacenamiento privado…");
      const put = await fetch(upload.upload_url, { method: "PUT", headers: { "Content-Type": upload.content_type }, body: file });
      if (!put.ok) throw new Error("R2 rechazó la carga del video (HTTP " + put.status + ").");
      setMessage("Enviando trabajo al servicio GPU…");
      const started = await fetch("/api/fuentes/vision/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ object_key: upload.object_key }),
      });
      const job = await started.json();
      if (!started.ok || !job.job_id) throw new Error(job.error || "No se pudo iniciar el trabajo GPU.");
      let completed = false;
      for (let attempt = 0; attempt < 120; attempt++) {
        await new Promise(resolve => window.setTimeout(resolve, 5000));
        const poll = await fetch("/api/fuentes/vision/jobs/" + encodeURIComponent(job.job_id));
        const state = await poll.json();
        if (!poll.ok) throw new Error(state.error || "No se pudo consultar el trabajo GPU.");
        if (state.status === "COMPLETED") {
          const output = state.output as VisionResult;
          if (output?.status === "error") throw new Error(output.error || "Falló la inferencia.");
          setResult(output); setMessage("Análisis terminado."); completed = true; break;
        }
        if (state.status === "FAILED" || state.status === "CANCELLED" || state.status === "TIMED_OUT") {
          throw new Error(state.error || "El servicio GPU terminó el trabajo con estado " + state.status + ".");
        }
        setMessage("Procesando en GPU externa… estado: " + state.status);
      }
      if (!completed) throw new Error("El trabajo sigue pendiente. Revisá el estado en el proveedor RunPod antes de volver a enviarlo.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "No se pudo completar el análisis.");
    } finally { setWorking(false); }
  }

  if (config?.status === "pausado") return <section className="dt-panel" style={{ marginTop: 14 }}>
    <h3>Visión artificial ganadera · análisis de video</h3>
    <p className="dt-muted">Módulo en preparación. El conteo y seguimiento de bovinos en video se habilitará cuando pueda funcionar con herramientas gratuitas.</p>
  </section>;

  return <section className="dt-panel" style={{ marginTop: 14 }}>
    <h3>Visión artificial ganadera · análisis de video</h3>
    <p className="dt-muted">Carga privada a R2 y procesamiento remoto con GPU. Detecta bovinos y sigue sus trayectorias dentro del video.</p>
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
      <input type="file" accept="video/mp4,video/quicktime,.mp4,.mov,.m4v" onChange={e => { setFile(e.target.files?.[0] || null); setResult(null); setMessage(""); }} />
      <button className="dt-btn" disabled={!file || working || config?.status !== "ready"} onClick={() => void analyze()}>
        {working ? "Procesando…" : "Detectar y seguir ganado"}
      </button>
    </div>
    {file && <p className="dt-muted">Archivo seleccionado: {file.name} · {(file.size / 1048576).toFixed(1)} MB · máximo 100 MB</p>}
    {config && config.status !== "ready" && <div className="dt-alert">Servicio GPU sin configurar. Faltan variables: {(config.missing_environment || []).join(", ") || "conexión API"}. La interfaz no simula resultados.</div>}
    {message && <p role="status" className="dt-muted">{message}</p>}
    {result && <div className="dt-cards">
      <div className="dt-stat"><small>Detecciones bovinas en fotogramas</small><b>{result.cattle_detections ?? "—"}</b><span>Conteo acumulado, no cantidad única de animales</span></div>
      <div className="dt-stat"><small>Máximo en un fotograma</small><b>{result.max_cattle_in_frame ?? "—"}</b><span>Conteo simultáneo observado</span></div>
      <div className="dt-stat"><small>Tracks temporales</small><b>{result.unique_temporary_track_ids ?? "—"}</b><span>BoT-SORT · un video</span></div>
    </div>}
    {result && <p className="dt-source">Modelo: {result.model} · dispositivo: {result.device} · duración: {result.video_duration_seconds}s · fotogramas muestreados: {result.sampled_frames}. {result.limitations?.join(" ")}</p>}
    <p className="dt-source">Los identificadores de seguimiento no son identidades permanentes. No se debe usar este resultado como registro sanitario o trazabilidad oficial sin validación y vinculación con caravanas/RFID.</p>
  </section>;
}
