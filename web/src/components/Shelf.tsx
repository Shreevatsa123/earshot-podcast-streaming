import { useRef } from "react";
import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  title: string;
  subtitle?: string;
  children: ReactNode;
}

/** A titled, horizontally scrolling row of cards with left/right buttons. */
export function Shelf({ title, subtitle, children }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  const scrollBy = (direction: -1 | 1) => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollBy({ left: direction * Math.max(320, el.clientWidth * 0.78), behavior: "smooth" });
  };

  const arrowClass =
    "w-9 h-9 rounded-lg flex items-center justify-center bg-[#1A0E2F]/90 hover:bg-[#2A174B] border border-purple-300/12 text-[#D8B4FE] transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400";

  return (
    <section className="relative py-5 sm:py-6" aria-label={title}>
      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12">
        <div className="flex items-end justify-between gap-4 mb-4">
          <div className="min-w-0">
            <h2 className="font-display text-xl sm:text-2xl font-bold tracking-tight text-[#FAF7FF] truncate">
              {title}
            </h2>
            {subtitle && <p className="text-xs sm:text-sm text-[#A996C7] mt-0.5">{subtitle}</p>}
          </div>
          <div className="hidden sm:flex items-center gap-2 shrink-0">
            <button type="button" onClick={() => scrollBy(-1)} aria-label={`Scroll ${title} left`} className={arrowClass}>
              <ChevronLeft className="w-4 h-4" aria-hidden="true" />
            </button>
            <button type="button" onClick={() => scrollBy(1)} aria-label={`Scroll ${title} right`} className={arrowClass}>
              <ChevronRight className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div
          ref={scrollerRef}
          className="flex gap-4 sm:gap-5 overflow-x-auto no-scrollbar pb-3 pt-1 -mx-1 px-1 snap-x snap-mandatory"
        >
          {children}
        </div>
      </div>
    </section>
  );
}
