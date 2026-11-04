import { runCost } from "../credits";

// "This run costs 6 credits (3 per text × 2 texts)" plus a warning when the
// visitor can't afford it. `credits` is null when limits are off (local dev).
export default function CostNote({ costPerText, count = 1, credits, noModels }) {
  if (noModels) {
    return <p className="hint cost-note cost-blocked">Select at least one model above to run a prediction.</p>;
  }
  if (credits === null || credits === undefined) return null;

  const total = runCost(costPerText, count);
  const breakdown = count > 1 ? ` (${costPerText} per text × ${count} texts)` : "";
  const short = total > credits;
  return (
    <p className={`hint cost-note ${short ? "cost-blocked" : ""}`}>
      This run costs <strong>{total}</strong> credit{total === 1 ? "" : "s"}
      {breakdown}
      {short && ` - you have ${credits} left this hour`}
    </p>
  );
}
