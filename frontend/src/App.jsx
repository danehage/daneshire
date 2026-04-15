import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import WatchlistPage from "./pages/WatchlistPage";
import ScannerPage from "./pages/ScannerPage";
import TickerDetailPage from "./pages/TickerDetailPage";
import AlertsPage from "./pages/AlertsPage";
import JournalPage from "./pages/JournalPage";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/scanner" element={<ScannerPage />} />
          <Route path="/ticker/:symbol" element={<TickerDetailPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/journal" element={<JournalPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
