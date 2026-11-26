import { AlertTriangle, ArrowUpRight, Headphones, Radio, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import { useSession } from "../auth/session";

// Same three points as before; the layout follows the team's Nocturne login design.
const FEATURES = [
  { icon: RotateCcw, title: "Pick up where you left off", text: "Resume any episode at the second you paused." },
  { icon: Radio, title: "See what's trending now", text: "Live play counts from everyone listening." },
  { icon: Sparkles, title: "Recommendations for you", text: "Shows picked from what people like you play." },
];

// Facts about the catalog snapshot (contracts/samples/catalog.json, CONTEXT §8.3).
const HIGHLIGHTS = [
  { value: "48", label: "Real podcast shows" },
  { value: "958", label: "Episodes to play" },
  { value: "8", label: "Genres to browse" },
];

// Fixed heights (%) for the decorative sound bars on the card.
const WAVE_HEIGHTS = [34, 62, 48, 86, 58, 100, 44, 72, 90, 52, 66, 38, 80, 56, 42, 70, 50, 84, 40, 64];

/** Shown instead of the app when nobody is logged in (or the login failed). */
export function SignIn() {
  const { status, error, signIn } = useSession();
  const failed = status === "error";

  return (
    <div className="relative min-h-screen w-full flex flex-col overflow-hidden bg-[#07020F] text-[#FAF7FF]">
      {/* Layered purple light behind everything */}
      <div aria-hidden="true" className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0B0418] via-[#14072B] to-[#07020F]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_55%_48%_at_76%_24%,rgba(168,85,247,0.34),transparent_68%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_52%_44%_at_16%_80%,rgba(126,34,206,0.30),transparent_68%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_40%_35%_at_40%_10%,rgba(76,29,149,0.28),transparent_70%)]" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#07020F] via-transparent to-[#07020F]/60" />
      </div>

      <header className="relative z-20 w-full border-b border-purple-300/10 bg-[#090314]/55 backdrop-blur-md">
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 h-16 flex items-center">
          <span className="brand-gradient font-display text-xl sm:text-2xl font-extrabold tracking-[0.14em]">EARSHOT</span>
        </div>
      </header>

      <main className="relative z-10 flex-1 flex items-center py-12 sm:py-16 lg:py-20">
        <div className="max-w-[1340px] w-full mx-auto px-5 sm:px-8 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left: headline and the login button */}
          <div className="lg:col-span-7 space-y-8">
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs sm:text-sm font-medium text-[#D8B4FE]">
                <span className="inline-flex items-center gap-1.5 font-semibold text-[#F3E8FF]">
                  <Headphones className="w-4 h-4" aria-hidden="true" />
                  Every story, within earshot.
                </span>
                <span aria-hidden="true" className="text-purple-300/40">·</span>
                <span>Resume anywhere</span>
                <span aria-hidden="true" className="text-purple-300/40">·</span>
                <span>Live trending</span>
              </div>

              <h1 className="font-display text-[clamp(2.65rem,5.2vw,4.75rem)] font-extrabold leading-[1.02] tracking-tight text-[#FAF7FF] text-balance">
                Your podcasts, right where you left them.
              </h1>

              <p className="text-base sm:text-lg leading-relaxed text-[#DDD0F2] max-w-[54ch]">
                Log in to see your home page, keep listening across devices, and find out what everyone's playing today.
              </p>
            </div>

            {failed && (
              <p
                role="alert"
                className="flex items-start gap-2 max-w-xl rounded-2xl border border-[#C084FC]/30 bg-[#160A2C]/90 backdrop-blur-xl px-5 py-4 text-sm text-[#F5D0FE] shadow-[0_20px_50px_rgba(5,2,14,0.75)]"
              >
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                <span>
                  Login didn't finish{error ? `: ${error}` : "."} Try again.
                </span>
              </p>
            )}

            <div className="space-y-5 pt-2">
              <button
                type="button"
                onClick={signIn}
                className="group inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-xl bg-gradient-to-r from-[#A855F7] via-[#9333EA] to-[#7C3AED] hover:from-[#B76BFF] hover:via-[#A855F7] hover:to-[#8B5CF6] text-white font-display font-semibold text-base shadow-[0_14px_38px_rgba(147,51,234,0.48)] transition-all duration-150 active:scale-[0.98] whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
              >
                <span>Log in or sign up</span>
                <ArrowUpRight
                  className="w-4 h-4 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                  aria-hidden="true"
                />
              </button>

              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs sm:text-sm text-[#B39FD3]">
                <span className="inline-flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-[#C084FC]" aria-hidden="true" />
                  Secure sign-in with Amazon Cognito
                </span>
                <span aria-hidden="true" className="text-purple-300/35">·</span>
                <span>
                  New here? Choose <span className="text-[#E9D5FF]">Create an account</span> on the next page.
                </span>
              </div>
            </div>

            <dl className="grid grid-cols-3 gap-6 pt-6 border-t border-purple-300/12 max-w-xl">
              {HIGHLIGHTS.map(({ value, label }) => (
                <div key={label}>
                  <dt className="sr-only">{label}</dt>
                  <dd>
                    <p className="font-display text-2xl sm:text-3xl font-bold text-[#FAF7FF] tabular-nums">{value}</p>
                    <p className="text-xs text-[#A995C8] mt-1">{label}</p>
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Right: showcase card with Earshot's three features */}
          <div className="lg:col-span-5">
            <div className="relative">
              <div
                aria-hidden="true"
                className="absolute -inset-2 rounded-[28px] bg-gradient-to-br from-[#C084FC]/28 via-[#7E22CE]/18 to-[#4C1D95]/28 blur-2xl opacity-85 pointer-events-none"
              />

              <div className="relative rounded-2xl bg-gradient-to-b from-[#1B0D35]/92 via-[#140929]/95 to-[#0E061E]/96 border border-purple-300/20 backdrop-blur-xl overflow-hidden shadow-[0_30px_90px_rgba(4,1,12,0.88)]">
                <div
                  aria-hidden="true"
                  className="h-[2px] w-full bg-gradient-to-r from-transparent via-[#D8B4FE] to-transparent opacity-80"
                />

                {/* Decorative artwork: a glowing sound wave */}
                <div aria-hidden="true" className="relative aspect-[16/9] overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-[#3B0F70] via-[#1E0B3D] to-[#0E061E]" />
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_70%_at_50%_55%,rgba(192,132,252,0.45),transparent_70%)]" />
                  <div className="absolute inset-x-8 bottom-8 top-16 flex items-end justify-between gap-1.5">
                    {WAVE_HEIGHTS.map((h, i) => (
                      <span
                        key={i}
                        className="eq-bar flex-1 rounded-full bg-gradient-to-t from-[#9333EA] via-[#C084FC] to-[#F5D0FE] opacity-90"
                        style={{ height: `${h}%`, animationDelay: `${((i * 0.17) % 1.1).toFixed(2)}s` }}
                      />
                    ))}
                  </div>
                  <div className="absolute inset-0 bg-gradient-to-t from-[#140929] via-[#140929]/20 to-transparent" />
                  <span className="absolute top-4 left-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0D051B]/80 border border-purple-300/25 text-[11px] font-medium text-[#FAF7FF] backdrop-blur-md">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#E879F9]" />
                    Listening now
                  </span>
                </div>

                <div className="p-6 space-y-5">
                  <div>
                    <p className="text-xs font-medium text-[#C084FC]">Podcasts · Real-time listening</p>
                    <h2 className="font-display text-xl sm:text-2xl font-bold text-[#FAF7FF] mt-0.5">Listen on Earshot</h2>
                    <p className="text-xs sm:text-sm leading-relaxed text-[#CFC0E8] mt-2">
                      Every play is counted the moment it happens, so your place and the charts are always up to date.
                    </p>
                  </div>

                  <div className="pt-4 border-t border-purple-300/12 space-y-2">
                    <div className="flex items-center justify-between text-[11px] text-[#A28EC4]">
                      <span className="inline-flex items-center gap-1.5">
                        <Headphones className="w-3.5 h-3.5 text-[#C084FC]" aria-hidden="true" />
                        <span>What you get</span>
                      </span>
                      <span className="font-mono tabular-nums">0{FEATURES.length}</span>
                    </div>

                    <ul className="space-y-2">
                      {FEATURES.map(({ icon: Icon, title, text }, idx) => (
                        <li
                          key={title}
                          className="flex items-start gap-3 px-3.5 py-3 rounded-xl border bg-[#160B2B]/70 border-purple-300/10"
                        >
                          <span className="font-mono text-[10px] tabular-nums text-[#C084FC] pt-1 w-5 shrink-0">0{idx + 1}</span>
                          <div className="min-w-0 flex-1">
                            <h3 className="font-display text-sm font-semibold text-[#FAF7FF]">{title}</h3>
                            <p className="text-xs text-[#BFAEE0] mt-0.5">{text}</p>
                          </div>
                          <Icon className="w-4 h-4 text-[#D8B4FE] shrink-0 mt-0.5" aria-hidden="true" />
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="relative z-10 border-t border-purple-300/10 py-6">
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[#927DB5]">
          <span>
            <span className="brand-gradient font-display font-bold tracking-[0.14em]">EARSHOT</span>
            <span className="ml-3">Every story, within earshot.</span>
          </span>
          <span>© 2026 Earshot</span>
        </div>
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
