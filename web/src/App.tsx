import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { PlayerDock } from "./components/PlayerDock";
import { PlayerProvider, usePlayer } from "./components/PlayerContext";
import { SearchOverlay } from "./components/SearchOverlay";
import { ShowDetailModal } from "./components/ShowDetailModal";
import { UiContext, useUi } from "./components/UiContext";
import type { UiActions } from "./components/UiContext";
import { Home } from "./pages/Home";
import { Placeholder } from "./pages/Placeholder";
import { USE_MOCKS } from "./lib/config";

/** App shell: top bar, routed pages, footer, show dialog, search and the player dock. */
export function App() {
  const [detailShowId, setDetailShowId] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);

  const ui = useMemo<UiActions>(
    () => ({ openShow: setDetailShowId, openSearch: () => setSearchOpen(true) }),
    [],
  );
  const closeShow = useCallback(() => setDetailShowId(null), []);
  const closeSearch = useCallback(() => setSearchOpen(false), []);

  return (
    <PlayerProvider>
      <UiContext.Provider value={ui}>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route
              path="/browse"
              element={<Placeholder title="Browse by genre" note="All 8 genres and their shows. Coming in M1-06." />}
            />
            <Route
              path="/trending"
              element={
                <Placeholder title="Live Trending" note="Today's most-played episodes, refreshed every 5 seconds. Coming in M1-06." />
              }
            />
            <Route
              path="/settings"
              element={<Placeholder title="Settings" note="Pick the region your listening events come from. Coming in M1-06." />}
            />
            <Route path="*" element={<Placeholder title="Page not found" note="There's nothing at this address." />} />
          </Routes>
        </Layout>
        <ShowDetailModal showId={detailShowId} onClose={closeShow} />
        <SearchOverlay isOpen={searchOpen} onClose={closeSearch} />
        <PlayerDock />
        {USE_MOCKS && (
          <div className="pointer-events-none fixed right-3 top-[72px] z-30 rounded-md bg-gradient-to-r from-[#7E22CE] to-[#A855F7] px-2 py-1 text-[11px] font-bold tracking-wide text-white shadow-lg">
            MOCK DATA
          </div>
        )}
      </UiContext.Provider>
    </PlayerProvider>
  );
}

function Layout({ children }: { children: ReactNode }) {
  const { current } = usePlayer();
  return (
    <div className={`min-h-screen flex flex-col ${current ? "pb-24" : "pb-6"}`}>
      <Navbar />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}

function Footer() {
  const { openSearch } = useUi();
  const linkClass = "hover:text-[#E9D5FF] transition-colors";
  return (
    <footer className="mt-16 border-t border-purple-300/10 py-10">
      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs text-[#927DB5]">
        <div className="flex items-center gap-3">
          <span className="brand-gradient font-display font-bold tracking-[0.14em]">EARSHOT</span>
          <span>Every story, within earshot.</span>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-5">
          <Link to="/" className={linkClass}>
            Home
          </Link>
          <Link to="/browse" className={linkClass}>
            Browse
          </Link>
          <Link to="/trending" className={linkClass}>
            Live Trending
          </Link>
          <button type="button" onClick={openSearch} className={`${linkClass} cursor-pointer`}>
            Search
          </button>
          <span>© 2026 Earshot</span>
        </nav>
      </div>
    </footer>
  );
}
