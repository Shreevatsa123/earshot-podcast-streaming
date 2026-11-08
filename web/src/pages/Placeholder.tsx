/**
 * Placeholder pages for routes implemented in later M1 tasks:
 *   Browse        → M1-06 (GET /genres, GET /shows)
 *   Show detail   → M1-06 (GET /shows/{id})
 *   Live Trending → M1-06 (GET /trending, 5 s poll)
 *   Settings      → M1-06 (region picker)
 * The route wiring exists now so the shell is complete and navigable.
 */
export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div className="page">
      <h1>{title}</h1>
      <p className="muted">{note}</p>
    </div>
  );
}
