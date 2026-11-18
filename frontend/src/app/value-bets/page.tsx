"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getModels, getValueBets } from "@/lib/api";
import { Card, EmptyState, ErrorNote, SectionHeader, StatCard } from "@/components/ui";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import type { ModelInfo, ValueBet } from "@/types";

type SortKey = "edge" | "kelly" | "odds";

const OUTCOMES = [
  { key: "home_win", label: "Home" },
  { key: "draw", label: "Draw" },
  { key: "away_win", label: "Away" },
] as const;

const SELECTION_LABEL: Record<string, string> = {
  home_win: "Home",
  draw: "Draw",
  away_win: "Away",
};

interface Leg {
  key: string;
  label: string;
  odds: number;
  model: number;
  market: number | null;
  edge: number | null;
  flagged: boolean;
  book: string;
}

function legsFor(bet: ValueBet): Leg[] {
  if (bet.prices && bet.model_probs) {
    return OUTCOMES.map(({ key, label }) => {
      const odds = bet.prices![key];
      const model = bet.model_probs![key];
      const market = bet.fair_probs?.[key] ?? null;
      return {
        key,
        label,
        odds,
        model,
        market,
        edge: market === null ? null : model - market,
        flagged: bet.selection === key,
        book: bet.price_books?.[key] ?? bet.sportsbook,
      };
    }).filter((leg) => leg.odds > 1);
  }

  return [
    {
      key: bet.selection,
      label: SELECTION_LABEL[bet.selection] ?? bet.selection,
      odds: bet.best_odds,
      model: bet.model_prob,
      market: bet.implied_prob,
      edge: bet.edge,
      flagged: true,
      book: bet.sportsbook,
    },
  ];
}

export default function ValueBetsPage() {
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [date, setDate] = useState("");
  const [minEdgePct, setMinEdgePct] = useState(3);
  const [sportsbook, setSportsbook] = useState("all");
  const [sortBy, setSortBy] = useState<SortKey>("edge");

  useEffect(() => {
    getModels()
      .then((data) => setModelInfo(data.models[0] ?? null))
      .catch(() => setModelInfo(null));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await getValueBets(date || undefined, minEdgePct / 100);
        if (!cancelled) {
          setValueBets(data.value_bets);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("Could not load the board. The backend did not answer.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [date, minEdgePct]);

  const sportsbooks = useMemo(
    () => [...new Set(valueBets.map((bet) => bet.sportsbook))].sort(),
    [valueBets]
  );

  const rows = useMemo(() => {
    const filtered = valueBets.filter(
      (bet) => sportsbook === "all" || bet.sportsbook === sportsbook
    );
    const sorted = [...filtered];
    if (sortBy === "edge") sorted.sort((a, b) => b.edge - a.edge);
    if (sortBy === "kelly") sorted.sort((a, b) => b.kelly_stake_pct - a.kelly_stake_pct);
    if (sortBy === "odds") sorted.sort((a, b) => b.best_odds - a.best_odds);
    return sorted;
  }, [valueBets, sportsbook, sortBy]);

  const summary = useMemo(() => {
    if (rows.length === 0) {
      return { count: 0, avgEdge: 0, avgOdds: 0, stake: 0 };
    }
    const total = rows.length;
    return {
      count: total,
      avgEdge:
        (rows.reduce((sum, bet) => sum + bet.edge, 0) / total) * 100,
      avgOdds: rows.reduce((sum, bet) => sum + bet.best_odds, 0) / total,
      stake: rows.reduce((sum, bet) => sum + bet.kelly_stake_pct, 0),
    };
  }, [rows]);

  return (
    <div className="animate-rise">
      <SectionHeader
        title="Model vs market"
        description="Every price the model disagrees with, on the last captured odds snapshot. The price is the best one on offer across the books captured; the market probability is the sharpest book's, with the bookmaker margin removed."
        actions={
          <DataSourceBadge
            label="the-odds-api"
            detail="free tier, prices captured as of the snapshot date"
            tone="mixed"
          />
        }
      />

      {error ? <ErrorNote>{error}</ErrorNote> : null}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Rows on the board" value={summary.count} note={`edge ≥ ${minEdgePct}%`} />
        <StatCard
          label="Average edge"
          value={`${summary.avgEdge >= 0 ? "+" : ""}${summary.avgEdge.toFixed(2)}%`}
          tone="accent"
          note="best-priced side per fixture"
        />
        <StatCard label="Average price" value={summary.avgOdds.toFixed(2)} note="decimal odds" />
        <StatCard
          label="Quarter-Kelly stake"
          value={`${summary.stake.toFixed(2)}%`}
          note="of bankroll across the board"
        />
      </div>

      <Card className="mb-6 p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
          <label className="block">
            <span className="text-xs text-ink-mute">Slate date</span>
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-ink outline-none focus:border-accent/60"
            />
          </label>

          <label className="block">
            <span className="text-xs text-ink-mute">Minimum edge: {minEdgePct}%</span>
            <input
              type="range"
              min={0}
              max={15}
              step={1}
              value={minEdgePct}
              onChange={(event) => setMinEdgePct(Number(event.target.value))}
              className="mt-3 w-full accent-accent"
            />
          </label>

          <label className="block">
            <span className="text-xs text-ink-mute">Sportsbook</span>
            <select
              value={sportsbook}
              onChange={(event) => setSportsbook(event.target.value)}
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-ink outline-none focus:border-accent/60"
            >
              <option value="all">All books</option>
              {sportsbooks.map((book) => (
                <option key={book} value={book}>
                  {book}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs text-ink-mute">Sort by</span>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as SortKey)}
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-ink outline-none focus:border-accent/60"
            >
              <option value="edge">Edge</option>
              <option value="kelly">Quarter-Kelly stake</option>
              <option value="odds">Price</option>
            </select>
          </label>
        </div>
      </Card>

      {loading ? (
        <Card className="px-6 py-14 text-center text-[13px] text-ink-soft">
          Pricing the board…
        </Card>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No disagreements above the threshold"
          description="Nothing on this slate prices far enough from the model to clear the edge you asked for. Lower the minimum edge or pick another date."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="hidden grid-cols-[minmax(220px,1.4fr)_repeat(3,minmax(120px,1fr))_minmax(150px,0.9fr)] border-b border-white/[0.07] px-5 py-3 lg:grid">
            {["Fixture", "Home", "Draw", "Away", "Book"].map((heading) => (
              <span key={heading} className="text-[11px] uppercase tracking-wide text-ink-mute">
                {heading}
              </span>
            ))}
          </div>

          <ul className="divide-y divide-white/[0.05]">
            {rows.map((bet) => (
              <li
                key={`${bet.match_id}-${bet.selection}`}
                className="grid grid-cols-1 gap-4 px-5 py-4 transition-colors duration-150 ease-out hover:bg-white/[0.02] lg:grid-cols-[minmax(220px,1.4fr)_repeat(3,minmax(120px,1fr))_minmax(150px,0.9fr)] lg:items-start"
              >
                <div className="min-w-0">
                  <Link
                    href={`/matches/${bet.match_id}`}
                    className="text-[14px] font-medium text-ink underline-offset-4 hover:underline"
                  >
                    {bet.home_team}
                    <span className="px-1.5 text-ink-mute">vs</span>
                    {bet.away_team}
                  </Link>
                  <p className="mt-1 font-mono text-[11px] text-ink-mute">
                    {bet.scheduled_at ? bet.scheduled_at.slice(0, 10) : "date unknown"}
                    {bet.odds_captured_at
                      ? ` · priced ${bet.odds_captured_at.slice(0, 10)}`
                      : ""}
                  </p>
                </div>

                {legsFor(bet).map((leg) => (
                  <div
                    key={leg.key}
                    className={
                      leg.flagged
                        ? "rounded-lg border-l-2 border-accent bg-accent/[0.06] px-3 py-2"
                        : "rounded-lg px-3 py-2"
                    }
                  >
                    <p className="flex items-baseline justify-between gap-2">
                      <span className="text-[11px] text-ink-mute lg:hidden">{leg.label}</span>
                      <span className="tnum font-mono text-[15px] text-ink">
                        {leg.odds.toFixed(2)}
                        <span className="ml-1 text-[10px] font-normal text-ink-mute">
                          {leg.book}
                        </span>
                      </span>
                    </p>
                    <p className="tnum mt-1 font-mono text-[11px] text-ink-soft">
                      {(leg.model * 100).toFixed(1)}%
                      <span className="text-ink-mute">
                        {" "}
                        model ·{" "}
                        {leg.market === null
                          ? "no market"
                          : `${(leg.market * 100).toFixed(1)}% market`}
                      </span>
                    </p>
                    {leg.edge === null ? null : (
                      <p
                        className={`tnum mt-1 font-mono text-[12px] ${
                          leg.edge > 0 ? "text-pos" : leg.edge < 0 ? "text-ink-mute" : "text-ink-soft"
                        }`}
                      >
                        {leg.edge > 0 ? "+" : ""}
                        {(leg.edge * 100).toFixed(2)}%
                      </p>
                    )}
                  </div>
                ))}

                <div className="flex items-center justify-between gap-3 lg:block">
                  <span className="text-[13px] text-ink-soft">{bet.sportsbook}</span>
                  <p className="tnum mt-1 font-mono text-[11px] text-ink-mute">
                    stake {bet.kelly_stake_pct.toFixed(2)}%
                  </p>
                  {bet.reference_sportsbook &&
                  bet.reference_sportsbook !== bet.sportsbook ? (
                    <p className="mt-1 font-mono text-[11px] text-ink-mute">
                      market ref {bet.reference_sportsbook}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <p className="mt-6 max-w-3xl text-[11px] leading-relaxed text-ink-mute">
        Model:{" "}
        {modelInfo
          ? `${modelInfo.version}, ${(modelInfo.accuracy * 100).toFixed(1)}% held-out accuracy${
              modelInfo.accuracy_base_rate != null
                ? ` against a ${(modelInfo.accuracy_base_rate * 100).toFixed(1)}% base rate`
                : ""
            }`
          : "unknown"}
        {" · "}
        Prices are a snapshot, not a live feed. A large edge usually means the model is
        wrong, not that the book is wrong.
      </p>
    </div>
  );
}
