import { useState } from "react";
import CostNote from "./CostNote";
import { runCost } from "../credits";

export default function MultiLineForm({ onSubmit, loading, costPerText, credits, noModels, maxRows }) {
  const [text, setText] = useState("");
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const tooMany = maxRows && lines.length > maxRows;
  const cantAfford = credits !== null && runCost(costPerText, lines.length) > credits;

  function handleSubmit(e) {
    e.preventDefault();
    if (lines.length > 0) onSubmit(lines);
  }

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <textarea
        rows={8}
        placeholder="Paste multiple lines of text, one input per line..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <p className={`hint ${tooMany ? "cost-blocked" : ""}`}>
        {lines.length} line{lines.length === 1 ? "" : "s"} detected{maxRows ? ` (max ${maxRows})` : ""}
      </p>
      {lines.length > 0 && (
        <CostNote costPerText={costPerText} count={lines.length} credits={credits} noModels={noModels} />
      )}
      <button type="submit" disabled={loading || lines.length === 0 || tooMany || noModels || cantAfford}>
        {loading ? "Predicting..." : "Predict all"}
      </button>
    </form>
  );
}
