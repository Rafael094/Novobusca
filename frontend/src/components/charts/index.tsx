"use client";

/**
 * Dependency-free SVG charts (no external chart library required).
 * Real data only — each chart renders exactly the series it is given.
 */

// --- Donut ------------------------------------------------------------------
export type DonutSlice = { label: string; value: number; color?: string };

const DEFAULT_COLORS = ["#2563eb", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#94a3b8"];

export function DonutChart({
  data,
  size = 180,
  thickness = 22,
  centerLabel,
  centerValue,
}: {
  data: DonutSlice[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string | number;
}) {
  const total = data.reduce((acc, d) => acc + d.value, 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-6">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#eef2f7"
            strokeWidth={thickness}
          />
          {total > 0 &&
            data.map((d, i) => {
              const fraction = d.value / total;
              const dash = fraction * circumference;
              const el = (
                <circle
                  key={d.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={d.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
                  strokeWidth={thickness}
                  strokeDasharray={`${dash} ${circumference - dash}`}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                />
              );
              offset += dash;
              return el;
            })}
        </g>
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          className="fill-slate-800"
          style={{ fontSize: 22, fontWeight: 700 }}
        >
          {centerValue ?? total.toLocaleString("pt-BR")}
        </text>
        {centerLabel && (
          <text
            x="50%"
            y="60%"
            textAnchor="middle"
            className="fill-slate-400"
            style={{ fontSize: 11 }}
          >
            {centerLabel}
          </text>
        )}
      </svg>
      <ul className="space-y-2">
        {data.map((d, i) => (
          <li key={d.label} className="flex items-center gap-2 text-sm">
            <span
              className="h-3 w-3 rounded-sm"
              style={{
                background: d.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
              }}
            />
            <span className="text-slate-600">{d.label}</span>
            <span className="font-medium text-slate-800">
              {d.value.toLocaleString("pt-BR")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// --- Line / area chart ------------------------------------------------------
export type LineSeries = { name: string; color: string; values: number[] };

export function LineChart({
  labels,
  series,
  height = 220,
}: {
  labels: string[];
  series: LineSeries[];
  height?: number;
}) {
  const width = 640;
  const padding = { top: 16, right: 16, bottom: 28, left: 36 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const allValues = series.flatMap((s) => s.values);
  const max = Math.max(1, ...allValues);
  const stepX = labels.length > 1 ? innerW / (labels.length - 1) : innerW;

  const x = (i: number) => padding.left + i * stepX;
  const y = (v: number) => padding.top + innerH - (v / max) * innerH;

  const ticks = 4;

  return (
    <div className="w-full overflow-x-auto scrollbar-thin">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {/* grid + y labels */}
        {Array.from({ length: ticks + 1 }).map((_, i) => {
          const val = (max / ticks) * i;
          const gy = y(val);
          return (
            <g key={i}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={gy}
                y2={gy}
                stroke="#eef2f7"
              />
              <text
                x={padding.left - 6}
                y={gy + 3}
                textAnchor="end"
                className="fill-slate-400"
                style={{ fontSize: 10 }}
              >
                {Math.round(val).toLocaleString("pt-BR")}
              </text>
            </g>
          );
        })}

        {/* x labels */}
        {labels.map((l, i) => (
          <text
            key={l}
            x={x(i)}
            y={height - 8}
            textAnchor="middle"
            className="fill-slate-400"
            style={{ fontSize: 10 }}
          >
            {l}
          </text>
        ))}

        {/* series */}
        {series.map((s) => {
          const points = s.values
            .map((v, i) => `${x(i)},${y(v)}`)
            .join(" ");
          return (
            <g key={s.name}>
              <polyline
                points={points}
                fill="none"
                stroke={s.color}
                strokeWidth={2.5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {s.values.map((v, i) => (
                <circle key={i} cx={x(i)} cy={y(v)} r={3} fill={s.color} />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-4">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-2 text-sm text-slate-600">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

// --- Gauge (risk score circle) ---------------------------------------------
export function GaugeChart({
  value,
  label,
  size = 160,
  color = "#2563eb",
}: {
  value: number;
  label?: string;
  size?: number;
  color?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const thickness = 14;
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#eef2f7"
          strokeWidth={thickness}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeDasharray={`${dash} ${circumference - dash}`}
          strokeLinecap="round"
        />
      </g>
      <text
        x="50%"
        y="47%"
        textAnchor="middle"
        className="fill-slate-800"
        style={{ fontSize: 30, fontWeight: 700 }}
      >
        {clamped}
      </text>
      {label && (
        <text
          x="50%"
          y="62%"
          textAnchor="middle"
          className="fill-slate-400"
          style={{ fontSize: 11 }}
        >
          {label}
        </text>
      )}
    </svg>
  );
}
