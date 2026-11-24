/**
 * Pages built in later M1 tasks. The routes exist now so the navigation works:
 *   Browse        → M1-06 (GET /genres, GET /shows)
 *   Live Trending → M1-06 (GET /trending, 5 s poll)
 *   Settings      → M1-06 (region picker for the demo)
 */
export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <section className="pt-28 sm:pt-32 pb-24 border-b border-purple-300/10">
      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12">
        <p className="text-xs font-medium text-[#C084FC] mb-2">Earshot</p>
        <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight text-[#FAF7FF] mb-3">{title}</h1>
        <p className="text-sm text-[#A995C8] max-w-xl">{note}</p>
      </div>
    </section>
  );
}
