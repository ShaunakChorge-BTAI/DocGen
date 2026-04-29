import { useState, useEffect } from "react";
import {
  LineChart, Line,
  BarChart, Bar,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useAuth } from "../contexts/AuthContext";
import { getAnalytics } from "../services/api";

// Brand-consistent palette
const COLORS = ["#2E7DB2", "#27ae60", "#e67e22", "#8e44ad", "#c0392b", "#16a085", "#f39c12"];

function SummaryCard({ label, value, unit = "" }) {
  return (
    <div className="analytics-card">
      <div className="analytics-card-value">
        {value ?? "—"}
        {value != null && unit && <span className="analytics-unit">{unit}</span>}
      </div>
      <div className="analytics-card-label">{label}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="analytics-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export default function AnalyticsDashboard({ addToast }) {
  const { authHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalytics(authHeaders)
      .then(setData)
      .catch((e) => addToast(e.message, "error"))
      .finally(() => setLoading(false));
  }, [authHeaders, addToast]);

  if (loading) return <div className="analytics-loading">Loading analytics…</div>;
  if (!data) return null;

  const { summary, docs_per_day, by_type, by_status, top_keywords, avg_time_per_day } = data;

  return (
    <div className="analytics-dashboard">
      <div className="analytics-header">
        <h2>📊 Analytics Dashboard</h2>
        <p>Generation metrics and usage trends across all documents.</p>
      </div>

      {/* ── Summary cards ── */}
      <div className="analytics-cards">
        <SummaryCard label="Total Documents" value={summary.total_docs} />
        <SummaryCard label="This Week" value={summary.docs_this_week} />
        <SummaryCard
          label="Avg Generation Time"
          value={summary.avg_generation_time}
          unit="s"
        />
        <SummaryCard label="Most Used Type" value={summary.most_used_type} />
      </div>

      {/* ── Docs per day ── */}
      <Section title="Documents Generated (Last 30 Days)">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={docs_per_day} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8f0f8" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#2E7DB2"
              strokeWidth={2}
              dot={false}
              name="Docs"
            />
          </LineChart>
        </ResponsiveContainer>
      </Section>

      {/* ── Avg generation time per day ── */}
      <Section title="Avg Generation Time per Day (s)">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={avg_time_per_day} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8f0f8" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
            <YAxis tick={{ fontSize: 11 }} unit="s" />
            <Tooltip formatter={(v) => [`${v}s`, "Avg time"]} />
            <Line
              type="monotone"
              dataKey="avg_seconds"
              stroke="#e67e22"
              strokeWidth={2}
              dot={false}
              name="Avg (s)"
            />
          </LineChart>
        </ResponsiveContainer>
      </Section>

      {/* ── By type + by status side-by-side ── */}
      <div className="analytics-row">
        <Section title="By Document Type">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={by_type}
                dataKey="count"
                nameKey="doc_type"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ doc_type, percent }) =>
                  `${doc_type} ${(percent * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {by_type.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v, n) => [v, n]} />
            </PieChart>
          </ResponsiveContainer>
        </Section>

        <Section title="By Status">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={by_status} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8f0f8" />
              <XAxis dataKey="status" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" name="Count" radius={[4, 4, 0, 0]}>
                {by_status.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Section>
      </div>

      {/* ── Top keywords ── */}
      <Section title="Top Instruction Keywords">
        <div className="keyword-grid">
          {top_keywords.map(({ word, count }, i) => (
            <div key={word} className="keyword-item">
              <span className="keyword-rank">#{i + 1}</span>
              <span className="keyword-word">{word}</span>
              <span className="keyword-count">{count}×</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
