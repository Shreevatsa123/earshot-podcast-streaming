import { Route, Routes } from "react-router-dom";
import { TopBar } from "./components/TopBar";
import { PlayerBar } from "./components/PlayerBar";
import { PlayerProvider } from "./components/PlayerContext";
import { Home } from "./pages/Home";
import { Placeholder } from "./pages/Placeholder";
import { USE_MOCKS } from "./lib/config";

/** App shell: fixed top bar, routed content, persistent player bar. */
export function App() {
  return (
    <PlayerProvider>
      <div className="app">
        <TopBar />
        <main className="content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route
              path="/browse"
              element={<Placeholder title="Browse" note="Genre browse arrives in M1-06." />}
            />
            <Route
              path="/shows/:showId"
              element={<Placeholder title="Show detail" note="Show detail arrives in M1-06." />}
            />
            <Route
              path="/trending"
              element={<Placeholder title="Live Trending" note="Live trending (5 s poll) arrives in M1-06." />}
            />
            <Route
              path="/settings"
              element={<Placeholder title="Settings" note="Region picker arrives in M1-06." />}
            />
            <Route path="*" element={<Placeholder title="Not found" note="No such page." />} />
          </Routes>
        </main>
        <PlayerBar />
        {USE_MOCKS && <div className="mock-flag">MOCK DATA</div>}
      </div>
    </PlayerProvider>
  );
}
