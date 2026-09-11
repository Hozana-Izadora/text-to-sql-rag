"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSpec } from "@/lib/types";

const CHART_COLORS = [
  "#6C5CE7", // violeta / accent
  "#00C48C", // esmeralda
  "#FFB020", // âmbar
  "#3B82F6", // azul
  "#FF6B81", // coral
  "#00D2D3", // ciano
];

const AXIS_TICK = { fontSize: 12, fill: "var(--text-secondary)" } as const;
const GRID_STROKE = "var(--border-subtle)";
const TOOLTIP_STYLE = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-subtle)",
  borderRadius: 8,
  color: "var(--text-primary)",
} as const;
const TOOLTIP_ITEM_STYLE = { color: "var(--text-primary)" } as const;

function formatValue(value: number, format?: string | null): string {
  if (format === "currency") {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

type ChartRow = Record<string, string | number>;

function buildRows(spec: ChartSpec): ChartRow[] {
  return spec.xData.map((label, index) => {
    const row: ChartRow = { name: label };
    for (const series of spec.series) {
      row[series.name] = series.values[index] ?? 0;
    }
    return row;
  });
}

interface ChartRendererProps {
  spec: ChartSpec;
}

export function ChartRenderer({ spec }: ChartRendererProps) {
  const data = buildRows(spec);
  const showLegend = spec.series.length > 1;

  const tooltipFormatter = (value: unknown, name: unknown): [string, string] => {
    const numericValue = typeof value === "number" ? value : Number(value);
    const seriesName = String(name);
    const series = spec.series.find((item) => item.name === seriesName);
    return [formatValue(numericValue, series?.valueFormat), seriesName];
  };

  const pieTooltipFormatter = (value: unknown): string => {
    const numericValue = typeof value === "number" ? value : Number(value);
    return formatValue(numericValue, spec.series[0]?.valueFormat);
  };

  return (
    <div className="mt-3 rounded-card border border-border-subtle bg-bg-surface p-3">
      <p className="mb-2 text-sm font-medium text-text-primary">{spec.title}</p>
      <ResponsiveContainer width="100%" height={280}>
        {spec.chartType === "pie" ? (
          <PieChart>
            <Pie
              data={spec.xData.map((label, index) => ({
                name: label,
                value: spec.series[0]?.values[index] ?? 0,
              }))}
              dataKey="value"
              nameKey="name"
              label
              animationDuration={600}
            >
              {spec.xData.map((label, index) => (
                <Cell key={label} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={pieTooltipFormatter}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              labelStyle={TOOLTIP_ITEM_STYLE}
            />
            <Legend />
          </PieChart>
        ) : spec.chartType === "line" ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
            <XAxis dataKey="name" tick={AXIS_TICK} />
            <YAxis tick={AXIS_TICK} />
            <Tooltip
              formatter={tooltipFormatter}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              labelStyle={TOOLTIP_ITEM_STYLE}
            />
            {showLegend && <Legend />}
            {spec.series.map((series, index) => (
              <Line
                key={series.name}
                type="monotone"
                dataKey={series.name}
                stroke={series.color || CHART_COLORS[index % CHART_COLORS.length]}
                animationDuration={600}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={data} layout={spec.chartType === "horizontal_bar" ? "vertical" : "horizontal"}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
            {spec.chartType === "horizontal_bar" ? (
              <>
                <XAxis type="number" tick={AXIS_TICK} />
                <YAxis type="category" dataKey="name" tick={AXIS_TICK} width={100} />
              </>
            ) : (
              <>
                <XAxis dataKey="name" tick={AXIS_TICK} />
                <YAxis tick={AXIS_TICK} />
              </>
            )}
            <Tooltip
              formatter={tooltipFormatter}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              labelStyle={TOOLTIP_ITEM_STYLE}
            />
            {showLegend && <Legend />}
            {spec.series.map((series, index) => (
              <Bar
                key={series.name}
                dataKey={series.name}
                fill={series.color || CHART_COLORS[index % CHART_COLORS.length]}
                animationDuration={600}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
