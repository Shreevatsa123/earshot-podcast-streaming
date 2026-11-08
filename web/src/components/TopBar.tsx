import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

const REGIONS = ["us-east", "us-west", "eu-west", "ap-south"] as const;

/**
 * Netflix-style top bar: transparent over the hero, fades to solid black on scroll.
 * The region selector is a demo control for events (CONTEXT §6 `region`); it is wired
 * into the event emitter in M1-08. Login/avatar becomes real in M1-05.
 */
export function TopBar() {
  const [scrolled, setScrolled] = useState(false);
  const [region, setRegion] = useState<string>(REGIONS[0]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`topbar${scrolled ? " topbar--scrolled" : ""}`}>
      <div className="brand">Earshot</div>
      <nav className="nav">
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/browse">Browse</NavLink>
        <NavLink to="/trending">Live</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      <div className="topbar__right">
        <select
          className="region-select"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          aria-label="Region"
        >
          {REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <div className="avatar" title="Account">
          E
        </div>
      </div>
    </header>
  );
}
