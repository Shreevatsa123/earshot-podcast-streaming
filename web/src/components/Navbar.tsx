import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Search } from "lucide-react";
import { useUi } from "./UiContext";

const NAV_ITEMS = [
  { to: "/", label: "Home", end: true },
  { to: "/browse", label: "Browse", end: false },
  { to: "/trending", label: "Live Trending", end: false },
  { to: "/settings", label: "Settings", end: false },
];

/**
 * Top bar in three zones: wordmark, page links, search. Transparent over the hero,
 * solid with a blur once the page scrolls.
 */
export function Navbar() {
  const { openSearch } = useUi();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `relative py-2 transition-colors duration-150 whitespace-nowrap shrink-0 rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-purple-400 ${
      isActive ? "text-white font-semibold" : "text-[#C8B9DF] hover:text-white"
    }`;

  return (
    <header
      className={`fixed top-0 inset-x-0 z-40 transition-colors duration-200 ${
        scrolled
          ? "bg-[#0B0515]/92 backdrop-blur-md border-b border-purple-300/10"
          : "bg-gradient-to-b from-[#090411]/90 via-[#090411]/45 to-transparent"
      }`}
    >
      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 h-16 flex items-center justify-between gap-8">
        <Link
          to="/"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="brand-gradient font-display text-xl sm:text-2xl font-extrabold tracking-[0.14em] whitespace-nowrap shrink-0 rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-purple-400"
        >
          EARSHOT
        </Link>

        <nav aria-label="Primary navigation" className="hidden md:flex items-center gap-7 text-sm font-medium">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
              {({ isActive }) => (
                <>
                  {item.label}
                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="absolute left-0 right-0 bottom-0 h-[2px] bg-gradient-to-r from-[#A855F7] via-[#D8B4FE] to-[#A855F7] rounded-full"
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center shrink-0">
          <button
            type="button"
            onClick={openSearch}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#F5F1FC] bg-[#241342]/80 hover:bg-[#311A59] border border-purple-300/15 rounded-lg transition-colors duration-150 whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
          >
            <Search className="w-4 h-4 text-[#D8B4FE]" aria-hidden="true" />
            <span>Search</span>
          </button>
        </div>
      </div>

      {/* Compact page switcher on small screens */}
      <nav
        aria-label="Mobile navigation"
        className="flex md:hidden items-center gap-5 px-5 pb-2.5 overflow-x-auto no-scrollbar text-xs font-medium border-b border-purple-300/10 bg-[#0B0515]/90"
      >
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `py-1 whitespace-nowrap shrink-0 transition-colors ${
                isActive ? "text-white font-semibold border-b-2 border-[#C084FC]" : "text-[#B9A7D4]"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
