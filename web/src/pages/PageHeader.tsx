import type { ReactNode } from "react";

/** Title band at the top of the non-Home pages, below the fixed top bar. */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow: ReactNode;
  title: string;
  subtitle?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="relative pt-28 sm:pt-32 pb-6 border-b border-purple-300/10 overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_55%_80%_at_15%_0%,rgba(126,34,206,0.30),transparent_70%)]"
      />
      <div className="relative max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="text-xs font-medium text-[#C084FC] mb-2">{eyebrow}</p>
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight text-[#FAF7FF]">{title}</h1>
          {subtitle && <p className="text-sm text-[#A995C8] mt-2 max-w-2xl">{subtitle}</p>}
        </div>
        {children}
      </div>
    </section>
  );
}

export function PageMessage({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 py-16 text-center text-sm text-[#A894C9]">{children}</div>
  );
}
