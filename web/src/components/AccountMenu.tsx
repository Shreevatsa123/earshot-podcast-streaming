import { useEffect, useRef, useState } from "react";
import { LogOut } from "lucide-react";
import { useSession } from "../auth/session";

/** Avatar with the user's initial; opens a small menu with their email and Log out. */
export function AccountMenu() {
  const { email, isMock, signOut } = useSession();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const initial = (email?.trim()[0] ?? "?").toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Account"
        aria-haspopup="menu"
        aria-expanded={open}
        className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#7E22CE] to-[#A855F7] text-white font-display font-bold text-sm flex items-center justify-center cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
      >
        {initial}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-64 rounded-xl bg-[#160B29] border border-purple-300/18 shadow-[0_18px_50px_rgba(4,1,12,0.8)] p-2"
        >
          <div className="px-3 py-2.5 border-b border-purple-300/10 mb-1">
            <p className="text-[11px] text-[#9D87BE]">Signed in as</p>
            <p className="text-sm font-medium text-[#F3ECFF] truncate">{email ?? "Unknown"}</p>
          </div>
          {isMock ? (
            <p className="px-3 py-2 text-xs text-[#A995C8]">Demo account (mock data). There's nothing to log out of.</p>
          ) : (
            <button
              type="button"
              role="menuitem"
              onClick={signOut}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-[#E4D9F7] hover:bg-[#241242] transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4 text-[#D8B4FE]" aria-hidden="true" />
              Log out
            </button>
          )}
        </div>
      )}
    </div>
  );
}
