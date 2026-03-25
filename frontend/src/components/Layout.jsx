import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

const navItems = [
  { path: "/", label: "Dashboard" },
  { path: "/watchlist", label: "Watchlist" },
  { path: "/scanner", label: "Scanner" },
  { path: "/alerts", label: "Alerts" },
];

function TickerSearch() {
  const [ticker, setTicker] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (ticker.trim()) {
      navigate(`/ticker/${ticker.trim().toUpperCase()}`);
      setTicker("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex">
      <input
        type="text"
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder="AAPL"
        className="w-20 px-2 py-1 text-sm border-2 border-ink bg-warm-white font-mono uppercase"
        maxLength={5}
      />
      <button
        type="submit"
        className="px-2 py-1 text-sm bg-ink text-warm-white border-2 border-ink hover:bg-dark-brown"
      >
        Go
      </button>
    </form>
  );
}

export default function Layout({ children }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-cream">
      <nav className="bg-warm-white border-b-2 border-ink">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <Link
              to="/"
              className="text-xl font-serif font-bold text-ink tracking-tight"
            >
              Danecast
            </Link>
            <div className="flex items-center gap-4">
              <div className="flex">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 transition-all ${
                      location.pathname === item.path
                        ? "bg-warm-white border-ink text-ink"
                        : "border-transparent text-mid-brown hover:border-ink hover:text-ink"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
              <TickerSearch />
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
