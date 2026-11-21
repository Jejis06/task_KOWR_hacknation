// Cienki wrapper na Chart.js (MIT). Rejestrujemy tylko to, czego używamy (mniejszy bundle).
import { useEffect, useRef } from "react";
import {
  BarController, BarElement, CategoryScale, Chart, type ChartConfiguration, Filler, Legend, LinearScale,
  LineController, LineElement, PointElement, Tooltip,
} from "chart.js";

Chart.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale,
  Tooltip, Legend, Filler);
Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
Chart.defaults.color = "#3d4a40";

export const COLORS = {
  // norma = bursztyn (ta sama barwa w każdym wykresie), parowanie ET₀ = fiolet – odróżnia się od opadu i normy
  rain: "#2f6fb3", rainLight: "rgba(47,111,179,.35)", normal: "#b45309", et0: "#7c3aed",
  green: "#0a7d32", red: "#b3261e", grey: "#8a948c",
};

export function ChartBox({ config, height = 220, label }: { config: ChartConfiguration; height?: number; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current) return;
    const c = new Chart(canvas.current, {
      ...config,
      options: { responsive: true, maintainAspectRatio: false, animation: false, ...config.options },
    });
    const before = () => c.resize();
    window.addEventListener("beforeprint", before);
    return () => { window.removeEventListener("beforeprint", before); c.destroy(); };
  }, [config]);
  return (
    <div className="chart" style={{ height }}>
      <canvas ref={canvas} role="img" aria-label={label} />
    </div>
  );
}
