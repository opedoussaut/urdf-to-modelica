import { useMemo, useRef, useState } from "react";

/** Time-series plot of real simulation output: shared time axis, units, legend, crosshair with tooltip. */
export type Series = { name: string; color: string; t: number[]; y: number[]; dash?: string; width?: number };

const W = 720,
  H = 220,
  L = 58,
  R = 14,
  T = 14,
  B = 34;

function ticks(lo: number, hi: number, n = 5) {
  const span = hi - lo || 1,
    step0 = span / n,
    mag = 10 ** Math.floor(Math.log10(step0)),
    step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-6; v += step) out.push(+v.toFixed(12));
  return out;
}

const fmt = (v: number) => {
  const a = Math.abs(v);
  return a !== 0 && (a < 1e-3 || a >= 1e4) ? v.toExponential(1) : +v.toPrecision(4) + "";
};

export default function TimeChart({
  title,
  unit,
  series,
  bands,
  height = H,
}: {
  title: string;
  unit: string;
  series: Series[];
  bands?: { y: number; label: string }[];
  height?: number;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const { t0, t1, y0, y1 } = useMemo(() => {
    const ts = series.flatMap((s) => [s.t[0], s.t.at(-1)!]);
    const ys = series.flatMap((s) => s.y).concat((bands || []).map((b) => b.y));
    let lo = Math.min(...ys),
      hi = Math.max(...ys);
    if (hi - lo < 1e-9) {
      lo -= 1;
      hi += 1;
    }
    const pad = (hi - lo) * 0.08;
    return { t0: Math.min(...ts), t1: Math.max(...ts), y0: lo - pad, y1: hi + pad };
  }, [series, bands]);
  const h = height;
  const x = (t: number) => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (h - T - B);
  const path = (s: Series) => {
    const n = s.t.length,
      stride = Math.max(1, Math.floor(n / 900));
    let d = "";
    for (let i = 0; i < n; i += stride) d += (d ? "L" : "M") + x(s.t[i]).toFixed(1) + "," + y(s.y[i]).toFixed(1);
    return d;
  };
  const at = (s: Series, t: number) => {
    let i = s.t.findIndex((v) => v >= t);
    if (i < 0) i = s.t.length - 1;
    return s.y[i];
  };
  const move = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    if (px < L || px > W - R) return setCursor(null);
    setCursor(t0 + ((px - L) / (W - L - R)) * (t1 - t0));
  };
  return (
    <figure className="lab-chart">
      <figcaption>
        <strong>{title}</strong>
        <span className="lab-legend">
          {series.map((s) => (
            <span key={s.name}>
              <i style={{ background: s.color, opacity: s.dash ? 0.7 : 1 }} />
              {s.name}
            </span>
          ))}
        </span>
      </figcaption>
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${h}`}
        role="img"
        aria-label={`${title} (${unit}) - OpenModelica result`}
        onMouseMove={move}
        onMouseLeave={() => setCursor(null)}
      >
        {ticks(y0, y1).map((v) => (
          <g key={"y" + v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="grid" />
            <text x={L - 6} y={y(v) + 4} textAnchor="end">
              {fmt(v)}
            </text>
          </g>
        ))}
        {ticks(t0, t1, 6).map((v) => (
          <g key={"x" + v}>
            <line x1={x(v)} x2={x(v)} y1={T} y2={h - B} className="grid v" />
            <text x={x(v)} y={h - B + 16} textAnchor="middle">
              {fmt(v)}
            </text>
          </g>
        ))}
        <text x={W - R} y={h - 4} textAnchor="end" className="axis-label">
          time · s
        </text>
        <text x={8} y={T + 4} className="axis-label">
          {unit}
        </text>
        {(bands || []).map((b) => (
          <g key={b.label}>
            <line x1={L} x2={W - R} y1={y(b.y)} y2={y(b.y)} className="band" />
            <text x={W - R - 4} y={y(b.y) - 4} textAnchor="end" className="band-label">
              {b.label}
            </text>
          </g>
        ))}
        {series.map((s) => (
          <path
            key={s.name}
            d={path(s)}
            fill="none"
            stroke={s.color}
            strokeWidth={s.width || 2}
            strokeDasharray={s.dash}
            strokeLinejoin="round"
          />
        ))}
        {cursor !== null && (
          <g>
            <line x1={x(cursor)} x2={x(cursor)} y1={T} y2={h - B} className="cursor" />
            {series.map((s) => (
              <circle key={s.name} cx={x(cursor)} cy={y(at(s, cursor))} r={3.5} fill={s.color} />
            ))}
          </g>
        )}
      </svg>
      {cursor !== null && (
        <div className="lab-tooltip" style={{ left: `${(x(cursor) / W) * 100}%` }}>
          <b>t = {cursor.toFixed(3)} s</b>
          {series.map((s) => (
            <span key={s.name}>
              <i style={{ background: s.color }} /> {s.name}: {fmt(at(s, cursor))} {unit}
            </span>
          ))}
        </div>
      )}
    </figure>
  );
}
