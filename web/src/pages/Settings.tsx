import { Check, Globe2, LogOut, User } from "lucide-react";
import { useSession } from "../auth/session";
import { getConfig } from "../lib/config";
import { REGIONS, setRegion, useRegion } from "../lib/region";
import { PageHeader } from "./PageHeader";

/** Settings: the listening region (a demo control for events) and the account. */
export function Settings() {
  const region = useRegion();
  const { email, isMock, signOut } = useSession();
  const { stage } = getConfig();

  return (
    <>
      <PageHeader eyebrow="Settings" title="Settings" subtitle="Choose where your listening is counted, and manage your account." />

      <div className="max-w-3xl mx-auto px-5 sm:px-8 pt-8 space-y-8">
        <section aria-labelledby="region-heading" className="rounded-2xl bg-[#160B29]/85 border border-purple-300/12 p-6">
          <div className="flex items-start gap-3 mb-5">
            <span className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#7E22CE] to-[#A855F7] flex items-center justify-center shrink-0">
              <Globe2 className="w-5 h-5 text-white" aria-hidden="true" />
            </span>
            <div>
              <h2 id="region-heading" className="font-display text-lg font-bold text-[#FAF7FF]">
                Listening region
              </h2>
              <p className="text-sm text-[#B9A7D6]">
                Every play, pause and buffering moment is tagged with a region. Switch it to listen as if you were somewhere
                else. Handy for the demo's per-region quality alerts.
              </p>
            </div>
          </div>

          <div role="radiogroup" aria-labelledby="region-heading" className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {REGIONS.map((r) => {
              const isActive = r.id === region;
              return (
                <button
                  key={r.id}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  onClick={() => setRegion(r.id)}
                  className={`text-left flex items-center justify-between gap-3 px-4 py-3.5 rounded-xl border transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400 ${
                    isActive
                      ? "bg-[#2C1650] border-[#C084FC]/50 text-white"
                      : "bg-[#1C0E34]/60 hover:bg-[#261445] border-purple-300/12 text-[#D6C7EE]"
                  }`}
                >
                  <span>
                    <span className="block font-display text-sm font-semibold">{r.name}</span>
                    <span className="block text-xs text-[#A995C8]">
                      {r.note} · <span className="font-mono">{r.id}</span>
                    </span>
                  </span>
                  {isActive && <Check className="w-4 h-4 text-[#D8B4FE] shrink-0" aria-hidden="true" />}
                </button>
              );
            })}
          </div>
        </section>

        <section aria-labelledby="account-heading" className="rounded-2xl bg-[#160B29]/85 border border-purple-300/12 p-6">
          <div className="flex items-start gap-3 mb-5">
            <span className="w-10 h-10 rounded-lg bg-[#22113E] border border-purple-300/15 flex items-center justify-center shrink-0">
              <User className="w-5 h-5 text-[#D8B4FE]" aria-hidden="true" />
            </span>
            <div>
              <h2 id="account-heading" className="font-display text-lg font-bold text-[#FAF7FF]">
                Account
              </h2>
              <p className="text-sm text-[#B9A7D6]">{email ?? "Unknown"}</p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-4 text-sm mb-5">
            <div>
              <dt className="text-xs text-[#9D87BE]">Environment</dt>
              <dd className="text-[#F3ECFF] font-mono">{stage}</dd>
            </div>
            <div>
              <dt className="text-xs text-[#9D87BE]">Data</dt>
              <dd className="text-[#F3ECFF]">{isMock ? "Sample data" : "Live"}</dd>
            </div>
          </dl>
          {!isMock && (
            <button
              type="button"
              onClick={signOut}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#22113E] hover:bg-[#2E1852] border border-purple-300/18 text-sm font-medium text-[#E4D9F7] cursor-pointer"
            >
              <LogOut className="w-4 h-4 text-[#D8B4FE]" aria-hidden="true" />
              Log out
            </button>
          )}
        </section>
      </div>
    </>
  );
}
