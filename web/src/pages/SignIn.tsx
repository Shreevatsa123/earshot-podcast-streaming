import { AlertTriangle, Headphones, LogIn, Radio, RotateCcw, Sparkles } from "lucide-react";
import { useSession } from "../auth/session";

const FEATURES = [
  { icon: RotateCcw, title: "Pick up where you left off", text: "Resume any episode at the second you paused." },
  { icon: Radio, title: "See what's trending now", text: "Live play counts from everyone listening." },
  { icon: Sparkles, title: "Recommendations for you", text: "Shows picked from what people like you play." },
];

/** Shown instead of the app when nobody is logged in (or the login failed). */
export function SignIn() {
  const { status, error, signIn } = useSession();
  const failed = status === "error";

  return (
    <div className="min-h-screen flex flex-col">
      <header className="max-w-[1440px] w-full mx-auto px-5 sm:px-8 lg:px-12 h-16 flex items-center">
        <span className="brand-gradient font-display text-xl sm:text-2xl font-extrabold tracking-[0.14em]">EARSHOT</span>
      </header>

      <main className="flex-1 flex items-center">
        <div className="relative w-full max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 py-16 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -z-10 inset-0 bg-[radial-gradient(ellipse_60%_60%_at_20%_40%,rgba(126,34,206,0.35),transparent_70%)]"
          />
          <div className="lg:col-span-7">
            <p className="inline-flex items-center gap-2 text-sm font-medium text-[#D8B4FE] mb-5">
              <Headphones className="w-4 h-4" aria-hidden="true" />
              Every story, within earshot.
            </p>
            <h1 className="font-display text-[clamp(2.4rem,5vw,4.4rem)] font-extrabold leading-[1.04] tracking-tight text-[#FAF7FF] text-balance mb-5">
              Your podcasts, right where you left them.
            </h1>
            <p className="text-base sm:text-lg text-[#DCD0EE] max-w-[54ch] mb-9">
              Log in to see your home page, keep listening across devices, and find out what everyone's playing today.
            </p>

            {failed && (
              <p
                role="alert"
                className="flex items-start gap-2 max-w-xl rounded-lg border border-purple-300/20 bg-[#1C0E34]/80 px-4 py-3 mb-6 text-sm text-[#F5D0FE]"
              >
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                <span>
                  Login didn't finish{error ? `: ${error}` : "."} Try again.
                </span>
              </p>
            )}

            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={signIn}
                className="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-lg bg-[#F8F5FF] hover:bg-white text-[#120722] font-semibold text-[15px] transition-transform active:scale-[0.98] cursor-pointer shadow-[0_8px_30px_rgba(147,51,234,0.4)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
              >
                <LogIn className="w-4 h-4" aria-hidden="true" />
                Log in or sign up
              </button>
              <p className="text-sm text-[#A995C8]">
                New here? Choose <span className="text-[#E9D5FF]">Create an account</span> on the next page.
              </p>
            </div>
          </div>

          <ul className="lg:col-span-5 space-y-4">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li
                key={title}
                className="flex items-start gap-4 rounded-xl bg-[#160B29]/85 border border-purple-300/12 p-5"
              >
                <span className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#7E22CE] to-[#A855F7] flex items-center justify-center shrink-0">
                  <Icon className="w-5 h-5 text-white" aria-hidden="true" />
                </span>
                <div>
                  <h2 className="font-display text-base font-bold text-[#FAF7FF]">{title}</h2>
                  <p className="text-sm text-[#B9A7D6] mt-0.5">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </main>

      <footer className="border-t border-purple-300/10 py-8">
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 text-xs text-[#927DB5]">© 2026 Earshot</div>
      </footer>
    </div>
  );
}

/** Full-screen placeholder while the login state is being restored. */
export function SessionLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <span className="brand-gradient font-display text-2xl font-extrabold tracking-[0.14em] animate-pulse">EARSHOT</span>
    </div>
  );
}
