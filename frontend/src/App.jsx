import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import WatchlistPage from "./pages/WatchlistPage";
import ScannerPage from "./pages/ScannerPage";

function Dashboard() {
  return (
    <div className="py-12">
      <h1 className="text-4xl font-serif font-bold text-ink mb-4">
        Danecast Trades
      </h1>
      <p className="text-mid-brown text-lg font-serif">
        Stock research terminal for swing trading and options strategies.
      </p>
    </div>
  );
}

function Placeholder({ title }) {
  return (
    <div className="py-12">
      <h1 className="text-3xl font-serif font-bold text-ink mb-4">{title}</h1>
      <p className="text-mid-brown font-sans">Coming soon</p>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/scanner" element={<ScannerPage />} />
          <Route
            path="/ticker/:symbol"
            element={<Placeholder title="Ticker Detail" />}
          />
          <Route path="/alerts" element={<Placeholder title="Alerts" />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
