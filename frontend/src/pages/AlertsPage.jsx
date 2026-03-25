import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useAlerts,
  useCreateAlert,
  useDeleteAlert,
  useDismissAlert,
} from "../hooks/useAlerts";

const STATUS_TABS = [
  { key: "active", label: "Active" },
  { key: "triggered", label: "Triggered" },
  { key: "dismissed", label: "Dismissed" },
  { key: "expired", label: "Expired" },
];

const ALERT_TYPES = [
  { value: "price_cross", label: "Price Cross" },
  { value: "technical_signal", label: "Technical Signal" },
  { value: "date_reminder", label: "Date Reminder" },
];

const METRICS = [
  { value: "price", label: "Price" },
  { value: "rsi", label: "RSI" },
  { value: "hv_rank", label: "HV Rank" },
];

const OPERATORS = [
  { value: ">", label: ">" },
  { value: ">=", label: ">=" },
  { value: "<", label: "<" },
  { value: "<=", label: "<=" },
  { value: "==", label: "=" },
];

const PRIORITIES = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

const STATUS_COLORS = {
  active: "bg-accent text-warm-white",
  triggered: "bg-success text-warm-white",
  dismissed: "bg-light-brown text-warm-white",
  expired: "bg-mid-brown text-warm-white",
};

const PRIORITY_COLORS = {
  low: "bg-cream text-dark-brown",
  normal: "bg-warm-white text-ink",
  high: "bg-warning text-warm-white",
  urgent: "bg-error text-warm-white",
};

function formatCondition(condition) {
  if (!condition?.metric || !condition?.operator || condition?.value == null) {
    return "Invalid condition";
  }
  const { metric, operator, value } = condition;
  let valueStr = value;
  if (metric === "price") valueStr = `$${value}`;
  else if (metric === "rsi" || metric === "hv_rank") valueStr = `${value}%`;
  return `${metric} ${operator} ${valueStr}`;
}

function formatDate(dateString) {
  if (!dateString) return "—";
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function CreateAlertForm({ onClose }) {
  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [alertType, setAlertType] = useState("price_cross");
  const [metric, setMetric] = useState("price");
  const [operator, setOperator] = useState(">");
  const [value, setValue] = useState("");
  const [actionNote, setActionNote] = useState("");
  const [priority, setPriority] = useState("normal");

  const createAlert = useCreateAlert();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!ticker.trim() || !name.trim() || !value) return;

    createAlert.mutate(
      {
        ticker: ticker.trim().toUpperCase(),
        name: name.trim(),
        alert_type: alertType,
        condition: {
          metric,
          operator,
          value: parseFloat(value),
        },
        action_note: actionNote.trim() || null,
        priority,
      },
      { onSuccess: onClose }
    );
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="border-2 border-ink shadow-hard bg-warm-white p-6 mb-6"
    >
      <h2 className="text-lg font-serif font-bold text-ink mb-4">
        Create Alert
      </h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Ticker
          </label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL"
            maxLength={5}
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white font-mono uppercase"
            required
          />
        </div>

        <div className="col-span-2">
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Alert Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="AAPL breaks $200"
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white"
            required
          />
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Type
          </label>
          <select
            value={alertType}
            onChange={(e) => setAlertType(e.target.value)}
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white"
          >
            {ALERT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Metric
          </label>
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white"
          >
            {METRICS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Operator
          </label>
          <select
            value={operator}
            onChange={(e) => setOperator(e.target.value)}
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white"
          >
            {OPERATORS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Value
          </label>
          <input
            type="number"
            step="any"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={metric === "price" ? "200.00" : "30"}
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white font-mono"
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <div className="md:col-span-3">
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Action Note (optional)
          </label>
          <input
            type="text"
            value={actionNote}
            onChange={(e) => setActionNote(e.target.value)}
            placeholder="What to do when triggered..."
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white"
          />
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown mb-1">
            Priority
          </label>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="w-full px-3 py-2 border-2 border-ink bg-warm-white"
          >
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={createAlert.isPending}
          className="px-6 py-2 bg-accent text-warm-white font-medium uppercase tracking-wide border-2 border-ink shadow-hard hover:bg-accent-hover disabled:opacity-50"
        >
          {createAlert.isPending ? "Creating..." : "Create Alert"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-mid-brown hover:text-ink"
        >
          Cancel
        </button>
        {createAlert.isError && (
          <span className="text-error text-sm">
            Failed: {createAlert.error?.message || "Unknown error"}
          </span>
        )}
      </div>
    </form>
  );
}

function AlertRow({ alert }) {
  const [expanded, setExpanded] = useState(false);
  const deleteAlert = useDeleteAlert();
  const dismissAlert = useDismissAlert();

  const handleDelete = (e) => {
    e.stopPropagation();
    if (confirm(`Delete alert "${alert.name}"?`)) {
      deleteAlert.mutate(alert.id);
    }
  };

  const handleDismiss = (e) => {
    e.stopPropagation();
    dismissAlert.mutate(alert.id);
  };

  return (
    <>
      <tr
        className={`border-b-2 border-ink hover:bg-warm-white transition-colors cursor-pointer ${
          expanded ? "bg-warm-white" : ""
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="py-3 px-4">
          <div className="flex items-center gap-2">
            <span
              className={`text-xs transition-transform ${
                expanded ? "rotate-90" : ""
              }`}
            >
              ▶
            </span>
            <Link
              to={`/ticker/${alert.ticker}`}
              onClick={(e) => e.stopPropagation()}
              className="font-serif text-lg text-ink hover:text-accent"
            >
              {alert.ticker}
            </Link>
          </div>
        </td>
        <td className="py-3 px-4">
          <span className="font-medium text-ink">{alert.name}</span>
        </td>
        <td className="py-3 px-4">
          <span className="font-mono text-sm text-mid-brown">
            {formatCondition(alert.condition)}
          </span>
        </td>
        <td className="py-3 px-4">
          <span
            className={`text-xs px-2 py-1 border border-ink uppercase tracking-wide ${
              STATUS_COLORS[alert.status]
            }`}
          >
            {alert.status}
          </span>
        </td>
        <td className="py-3 px-4">
          <span
            className={`text-xs px-2 py-1 border border-ink uppercase tracking-wide ${
              PRIORITY_COLORS[alert.priority]
            }`}
          >
            {alert.priority}
          </span>
        </td>
        <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
          <div className="flex gap-2 justify-end">
            {alert.status === "active" && (
              <button
                onClick={handleDismiss}
                disabled={dismissAlert.isPending}
                className="text-xs px-2 py-1 text-mid-brown hover:text-ink border border-light-brown hover:border-ink"
              >
                Dismiss
              </button>
            )}
            <button
              onClick={handleDelete}
              disabled={deleteAlert.isPending}
              className="text-light-brown hover:text-error font-bold text-lg"
            >
              {deleteAlert.isPending ? "..." : "×"}
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-cream border-b-2 border-ink">
          <td colSpan={6} className="px-6 py-4">
            <div className="grid grid-cols-3 gap-6 text-sm">
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                  Details
                </h4>
                <p>
                  <span className="text-mid-brown">Type:</span>{" "}
                  {alert.alert_type.replace("_", " ")}
                </p>
                <p>
                  <span className="text-mid-brown">Created:</span>{" "}
                  {formatDate(alert.created_at)}
                </p>
                {alert.triggered_at && (
                  <p>
                    <span className="text-mid-brown">Triggered:</span>{" "}
                    {formatDate(alert.triggered_at)}
                  </p>
                )}
                {alert.expires_at && (
                  <p>
                    <span className="text-mid-brown">Expires:</span>{" "}
                    {formatDate(alert.expires_at)}
                  </p>
                )}
              </div>
              <div className="col-span-2">
                <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                  Action Note
                </h4>
                <p className="text-ink">
                  {alert.action_note || (
                    <span className="text-light-brown italic">No action note</span>
                  )}
                </p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function AlertsTable({ alerts }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="text-center py-12 text-mid-brown">
        No alerts to display
      </div>
    );
  }

  return (
    <div className="border-2 border-ink shadow-hard bg-warm-white overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b-2 border-ink bg-cream">
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Ticker
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Name
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Condition
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Status
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Priority
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AlertsPage() {
  const [activeTab, setActiveTab] = useState("active");
  const [showForm, setShowForm] = useState(false);
  const { data: alerts, isLoading, error } = useAlerts(activeTab);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-4xl text-ink mb-2">Alerts</h1>
          <p className="text-mid-brown">
            Get notified when conditions are met
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="px-6 py-3 bg-accent text-warm-white font-medium uppercase tracking-wide border-2 border-ink shadow-hard hover:bg-accent-hover"
          >
            + New Alert
          </button>
        )}
      </div>

      {showForm && <CreateAlertForm onClose={() => setShowForm(false)} />}

      <div className="flex gap-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 transition-all ${
              activeTab === tab.key
                ? "bg-warm-white border-ink text-ink"
                : "border-transparent text-mid-brown hover:border-ink hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-mid-brown">Loading alerts...</div>
      ) : error ? (
        <div className="border-2 border-error bg-error/10 p-4 text-error">
          Error loading alerts: {error.message}
        </div>
      ) : (
        <AlertsTable alerts={alerts} />
      )}
    </div>
  );
}
