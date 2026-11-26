import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Headphones,
  Play,
  Radio,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useSession } from "../auth/session";
import { LOGIN_COVERS } from "../lib/loginCovers";

// Earshot's three features. The card shows one at a time as a carousel; the layout follows
// the team's Nocturne login design. The visuals are illustrations, not live data: nothing
// can be loaded from the API before login (CONTEXT §7.1).
interface Feature {
  icon: LucideIcon;
  kicker: string;
  title: string;
  text: string;
  Visual: ComponentType;
}

const FEATURES: Feature[] = [
  {
    icon: RotateCcw,
    kicker: "Resume · Any device",
    title: "Pick up where you left off",
    text: "Resume any episode at the second you paused.",
    Visual: ResumeVisual,
  },
  {
    icon: Radio,
    kicker: "Live · Updated every few seconds",
    title: "See what's trending now",
    text: "Live play counts from everyone listening.",
    Visual: TrendingVisual,
  },
  {
    icon: Sparkles,
    kicker: "For you · Based on listening",
    title: "Recommendations for you",
    text: "Shows picked from what people like you play.",
    Visual: RecsVisual,
  },
];

// Facts about the catalog snapshot (contracts/samples/catalog.json, CONTEXT §8.3).
const HIGHLIGHTS = [
  { value: "48", label: "Real podcast shows" },
  { value: "958", label: "Episodes to play" },
  { value: "8", label: "Genres to browse" },
];

const SLIDE_MS = 5000;

/** Shown instead of the app when nobody is logged in (or the login failed). */
export function SignIn() {
  const { status, error, signIn, signUp } = useSession();
  const failed = status === "error";

  return (
    <div className="relative min-h-screen w-full flex flex-col overflow-hidden bg-[#07020F] text-[#FAF7FF]">
      <Backdrop />

      <header className="relative z-20 w-full border-b border-purple-300/10 bg-[#090314]/55 backdrop-blur-md">
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 h-16 flex items-center">
          <span className="brand-gradient font-display text-xl sm:text-2xl font-extrabold tracking-[0.14em]">EARSHOT</span>
        </div>
      </header>

      <main className="relative z-10 flex-1 flex items-center py-12 sm:py-16 lg:py-20">
        <div className="max-w-[1340px] w-full mx-auto px-5 sm:px-8 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left: headline and the two login buttons */}
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
              <div className="flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  onClick={signIn}
                  className="group inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-xl bg-gradient-to-r from-[#A855F7] via-[#9333EA] to-[#7C3AED] hover:from-[#B76BFF] hover:via-[#A855F7] hover:to-[#8B5CF6] text-white font-display font-semibold text-base shadow-[0_14px_38px_rgba(147,51,234,0.48)] transition-all duration-150 active:scale-[0.98] whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
                >
                  <span>Log in</span>
                  <ArrowUpRight
                    className="w-4 h-4 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                    aria-hidden="true"
                  />
                </button>

                <button
                  type="button"
                  onClick={signUp}
                  className="group inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-xl bg-[#FAF7FF] hover:bg-white text-[#120722] font-display font-semibold text-base shadow-[0_12px_32px_rgba(12,4,24,0.45)] transition-all duration-150 active:scale-[0.98] whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
                >
                  <span>Sign up</span>
                  <ArrowUpRight
                    className="w-4 h-4 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                    aria-hidden="true"
                  />
                </button>
              </div>

              <p className="inline-flex items-center gap-1.5 text-xs sm:text-sm text-[#B39FD3]">
                <ShieldCheck className="w-4 h-4 text-[#C084FC]" aria-hidden="true" />
                Secure sign-in with Amazon Cognito
              </p>
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

          {/* Right: showcase card with a carousel of the three features */}
          <div className="lg:col-span-5">
            <FeatureCarousel />
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

/**
 * A tilted wall of real podcast covers drifting slowly sideways, under a deep purple tint and
 * the two drifting glows. Covers that fail to load leave a plain purple tile.
 */
function Backdrop() {
  const rows = 6;
  const perRow = 10;
  return (
    <div aria-hidden="true" className="fixed inset-0 z-0 pointer-events-none overflow-hidden bg-[#07020F]">
      <div className="absolute left-1/2 top-1/2 w-[160vw] -translate-x-1/2 -translate-y-1/2 -rotate-[12deg]">
        <div className="collage-drift flex flex-col gap-3">
          {Array.from({ length: rows }, (_, r) => (
            <div key={r} className="flex gap-3" style={{ marginLeft: r % 2 ? "-4vw" : "0" }}>
              {Array.from({ length: perRow }, (_, c) => (
                <CoverTile key={c} src={LOGIN_COVERS[(r * perRow + c * 3 + r) % LOGIN_COVERS.length]} />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="absolute inset-0 bg-[#2E0B5C]/45 mix-blend-multiply" />
      <div className="absolute inset-0 bg-gradient-to-r from-[#07020F]/94 via-[#14072B]/80 to-[#0B0418]/70" />
      <div className="aurora-a absolute -top-[20%] right-[-10%] w-[70vw] h-[70vw] rounded-full bg-[radial-gradient(circle,rgba(168,85,247,0.28),transparent_65%)]" />
      <div className="aurora-b absolute bottom-[-30%] left-[-15%] w-[75vw] h-[75vw] rounded-full bg-[radial-gradient(circle,rgba(126,34,206,0.26),transparent_65%)]" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#07020F] via-transparent to-[#07020F]/70" />
    </div>
  );
}

function CoverTile({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="shrink-0 w-[13vw] aspect-square rounded-lg overflow-hidden bg-gradient-to-br from-violet-900 to-[#0B0514]">
      {!failed && (
        <img
          src={src}
          alt=""
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="w-full h-full object-cover"
        />
      )}
    </div>
  );
}

/**
 * Glowing card (Nocturne style) that shows one feature at a time. It moves on every 5 s,
 * pauses while hovered or focused, and the numbered rows below pick a slide directly.
 */
function FeatureCarousel() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (paused || reduceMotion) return;
    const timer = window.setInterval(() => setActive((i) => (i + 1) % FEATURES.length), SLIDE_MS);
    return () => window.clearInterval(timer);
  }, [paused]);

  const feature = FEATURES[active];

  return (
    <div
      className="relative"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div
        aria-hidden="true"
        className="absolute -inset-2 rounded-[28px] bg-gradient-to-br from-[#C084FC]/28 via-[#7E22CE]/18 to-[#4C1D95]/28 blur-2xl opacity-85 pointer-events-none"
      />

      <section
        aria-roledescription="carousel"
        aria-label="What you get with Earshot"
        className="relative rounded-2xl bg-gradient-to-b from-[#1B0D35]/92 via-[#140929]/95 to-[#0E061E]/96 border border-purple-300/20 backdrop-blur-xl overflow-hidden shadow-[0_30px_90px_rgba(4,1,12,0.88)]"
      >
        <div aria-hidden="true" className="h-[2px] w-full bg-gradient-to-r from-transparent via-[#D8B4FE] to-transparent opacity-80" />

        {/* Slide artwork: all three are stacked and cross-fade */}
        <div aria-hidden="true" className="relative aspect-[16/9] overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-[#3B0F70] via-[#1E0B3D] to-[#0E061E]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_70%_at_50%_55%,rgba(192,132,252,0.40),transparent_70%)]" />
          {FEATURES.map(({ title, Visual }, idx) => (
            <div
              key={title}
              className={`absolute inset-0 transition-opacity duration-700 ease-out ${idx === active ? "opacity-100" : "opacity-0"}`}
            >
              <Visual />
            </div>
          ))}
          <div className="absolute inset-0 bg-gradient-to-t from-[#140929] via-[#140929]/10 to-transparent" />
          <span className="absolute top-4 left-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0D051B]/80 border border-purple-300/25 text-[11px] font-medium text-[#FAF7FF] backdrop-blur-md">
            <span className="w-1.5 h-1.5 rounded-full bg-[#E879F9]" />
            Listening now
          </span>
        </div>

        <div className="p-6 space-y-5">
          <div aria-live="polite" key={feature.title} className="min-h-[5.5rem]">
            <p className="text-xs font-medium text-[#C084FC]">{feature.kicker}</p>
            <h2 className="font-display text-xl sm:text-2xl font-bold text-[#FAF7FF] mt-0.5">{feature.title}</h2>
            <p className="text-xs sm:text-sm leading-relaxed text-[#CFC0E8] mt-2">{feature.text}</p>
          </div>

          <div className="pt-4 border-t border-purple-300/12 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-[#A28EC4]">
              <span className="inline-flex items-center gap-1.5">
                <Headphones className="w-3.5 h-3.5 text-[#C084FC]" aria-hidden="true" />
                <span>What you get</span>
              </span>
              <span className="font-mono tabular-nums">
                0{active + 1} / 0{FEATURES.length}
              </span>
            </div>

            <div role="tablist" aria-label="Features" className="grid grid-cols-3 gap-2">
              {FEATURES.map(({ icon: Icon, title }, idx) => {
                const isSelected = idx === active;
                return (
                  <button
                    key={title}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    onClick={() => setActive(idx)}
                    className={`relative overflow-hidden text-left px-3 py-2.5 rounded-xl border transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-300 ${
                      isSelected
                        ? "bg-[#29144E] border-[#C084FC]/45 text-white"
                        : "bg-[#160B2B]/70 hover:bg-[#221140] border-purple-300/10 text-[#BFAEE0]"
                    }`}
                  >
                    <span className="flex items-center justify-between">
                      <span className="font-mono text-[10px] tabular-nums text-[#C084FC]">0{idx + 1}</span>
                      <Icon className="w-3.5 h-3.5 text-[#D8B4FE]" aria-hidden="true" />
                    </span>
                    <span className="block font-display text-xs font-semibold leading-snug mt-1 line-clamp-2">{title}</span>
                    {isSelected && (
                      <span
                        aria-hidden="true"
                        key={`${active}-${paused}`}
                        className={`absolute left-0 bottom-0 h-[2px] bg-gradient-to-r from-[#9333EA] to-[#E9D5FF] ${paused ? "w-full" : "carousel-progress"}`}
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// ---- slide illustrations (decorative, no data) ---------------------------------------

function ResumeVisual() {
  return (
    <div className="absolute inset-0 flex items-center justify-center px-10">
      <div className="w-full max-w-sm rounded-2xl bg-[#0D051B]/70 border border-purple-300/20 backdrop-blur-md p-5 shadow-[0_18px_50px_rgba(5,2,14,0.6)]">
        <div className="flex items-center gap-3">
          <span className="w-11 h-11 rounded-full bg-[#FAF7FF] text-[#120722] flex items-center justify-center shrink-0 shadow-[0_6px_24px_rgba(168,85,247,0.5)]">
            <Play className="w-4 h-4 fill-current ml-0.5" />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-[#D8B4FE]">Resumed at 18:42</p>
            <p className="font-display text-sm font-semibold text-[#FAF7FF]">Right where you paused</p>
          </div>
        </div>
        <div className="mt-4 h-1.5 rounded-full bg-purple-950/90 overflow-hidden">
          <div className="playhead-fill h-full rounded-full bg-gradient-to-r from-[#9333EA] via-[#C084FC] to-[#E9D5FF]" />
        </div>
        <div className="mt-1.5 flex justify-between font-mono text-[10px] text-[#A995C8]">
          <span>18:42</span>
          <span>46:10</span>
        </div>
      </div>
    </div>
  );
}

const TREND_BARS = [
  { rank: 1, h: 92 },
  { rank: 2, h: 74 },
  { rank: 3, h: 60 },
  { rank: 4, h: 46 },
  { rank: 5, h: 34 },
];

function TrendingVisual() {
  return (
    <div className="absolute inset-x-12 top-[4.5rem] bottom-6 flex items-end justify-center gap-4">
      {TREND_BARS.map(({ rank, h }, i) => (
        <div key={rank} className="relative flex-1 max-w-14" style={{ height: `${h}%` }}>
          <span className="rank-numeral absolute -top-8 left-1/2 -translate-x-1/2 text-3xl leading-none">{rank}</span>
          <span
            className="bar-breathe block w-full h-full rounded-t-lg bg-gradient-to-t from-[#7E22CE] via-[#A855F7] to-[#F0ABFC] shadow-[0_0_24px_rgba(192,132,252,0.35)]"
            style={{ animationDelay: `${(i * 0.3).toFixed(2)}s` }}
          />
        </div>
      ))}
    </div>
  );
}

// Dots and the lines between them, in a 100 × 56 box (the slide's 16:9 shape).
const NODES = [
  { x: 18, y: 34 },
  { x: 34, y: 18 },
  { x: 50, y: 30 },
  { x: 66, y: 16 },
  { x: 82, y: 32 },
  { x: 42, y: 44 },
  { x: 62, y: 42 },
];
const LINKS: [number, number][] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [2, 5],
  [2, 6],
  [5, 6],
  [6, 4],
];

function RecsVisual() {
  return (
    <svg viewBox="0 0 100 56" className="absolute inset-0 w-full h-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="recs-line" x1="0" x2="1">
          <stop offset="0%" stopColor="#9333EA" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#F0ABFC" stopOpacity="0.8" />
        </linearGradient>
      </defs>
      {LINKS.map(([a, b]) => (
        <line
          key={`${a}-${b}`}
          x1={NODES[a].x}
          y1={NODES[a].y}
          x2={NODES[b].x}
          y2={NODES[b].y}
          stroke="url(#recs-line)"
          strokeWidth="0.5"
        />
      ))}
      {NODES.map(({ x, y }, i) => (
        <circle
          key={i}
          cx={x}
          cy={y}
          r={i === 2 ? 3 : 1.8}
          fill={i === 2 ? "#F5D0FE" : "#C084FC"}
          className="twinkle"
          style={{ animationDelay: `${(i * 0.35).toFixed(2)}s`, transformOrigin: `${x}px ${y}px` }}
        />
      ))}
    </svg>
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
