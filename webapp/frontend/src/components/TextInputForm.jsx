import { useState } from "react";
import CostNote from "./CostNote";
import { runCost } from "../credits";

export default function TextInputForm({ onSubmit, loading, costPerText, credits, noModels, maxChars }) {
  const [text, setText] = useState("");
  const tooLong = maxChars && text.trim().length > maxChars;
  const cantAfford = credits !== null && runCost(costPerText, 1) > credits;

  function handleSubmit(e) {
    e.preventDefault();
    if (text.trim()) onSubmit(text.trim());
  }

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <textarea
        rows={5}
        placeholder="Paste a headline or article text to classify..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {maxChars && (
        <p className={`hint ${tooLong ? "cost-blocked" : ""}`}>
          {text.trim().length} / {maxChars} characters
        </p>
      )}
      <CostNote costPerText={costPerText} credits={credits} noModels={noModels} />
      <button type="submit" disabled={loading || !text.trim() || tooLong || noModels || cantAfford}>
        {loading ? "Predicting..." : "Predict"}
      </button>
    </form>
  );
}
