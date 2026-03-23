import { Link, useLocation } from "react-router-dom";

const navItems = [
  { path: "/", label: "Dashboard" },
  { path: "/watchlist", label: "Watchlist" },
  { path: "/scanner", label: "Scanner" },
  { path: "/alerts", label: "Alerts" },
];

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
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
