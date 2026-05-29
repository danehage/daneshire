import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Dot,
} from "recharts";

function formatTimestamp(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
}

function formatValue(value) {
  if (value == null) return "—";
  return "$" + Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function CustomDot({ cx, cy, payload }) {
  if (payload?.source === "current") {
    return <circle cx={cx} cy={cy} r={5} fill="none" stroke="#8b4513" strokeWidth={2} />;
  }
  return <circle cx={cx} cy={cy} r={4} fill="#8b4513" />;
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="border-2 border-ink bg-warm-white px-3 py-2 text-xs font-mono shadow-hard-sm">
      <div className="font-bold text-ink">{formatValue(point.total_value)}</div>
      <div className="text-mid-brown">{formatTimestamp(point.timestamp)}</div>
      {point.cash_balance != null && (
        <div className="text-light-brown">cash: {formatValue(point.cash_balance)}</div>
      )}
      <div className="text-light-brown uppercase tracking-wide mt-0.5">{point.source}</div>
    </div>
  );
}

export default function ValueHistoryChart({ points }) {
  if (!points || points.length === 0) {
    return (
      <div className="p-8 text-center text-mid-brown font-mono text-sm">
        No snapshot history yet. Commit a snapshot to see value over time.
      </div>
    );
  }

  const data = points.map((p) => ({
    ...p,
    total_value_num: Number(p.total_value),
  }));

  const allValues = data.map((d) => d.total_value_num);
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const padding = (maxVal - minVal) * 0.1 || 1000;
  const yMin = Math.max(0, minVal - padding);
  const yMax = maxVal + padding;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
        <XAxis
          dataKey="timestamp"
          tickFormatter={formatTimestamp}
          tick={{ fontSize: 10, fontFamily: "monospace", fill: "#7c6658" }}
          tickLine={false}
          axisLine={{ stroke: "#1a0a00", strokeWidth: 2 }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[yMin, yMax]}
          tickFormatter={(v) =>
            "$" + (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0))
          }
          tick={{ fontSize: 10, fontFamily: "monospace", fill: "#7c6658" }}
          tickLine={false}
          axisLine={false}
          width={56}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="total_value_num"
          stroke="#8b4513"
          strokeWidth={2}
          dot={<CustomDot />}
          activeDot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
