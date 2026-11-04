import ConfidenceBar from "./ConfidenceBar";
import TokenHighlight from "./TokenHighlight";
import { CATEGORY_ORDER, MODEL_ACCENT_CLASS } from "../constants";

// `explain` is only passed for single-text results:
//   { onExplain, tokens, loading, credits }
// Batch rows render the card without it (no Explain button).
export default function ModelCard({ model, result, explain }) {
  const accentClass = MODEL_ACCENT_CLASS[model.family] || "";
  const explainCost = model.cost?.explain;
  const cantAfford = explain && explain.credits !== null && explainCost > explain.credits;

  return (
    <div className={`model-column ${accentClass}`}>
      <h3>{model.label}</h3>
      <div className="predicted-label">{result.predicted_label}</div>
      <div className="meta-row">
        <span className={`badge badge-${result.confidence_type}`}>
          {result.confidence_type === "margin_softmax" ? "margin-based" : "probability"}
        </span>
        <span className="badge badge-time">{result.inference_ms.toFixed(1)} ms</span>
      </div>
      <ConfidenceBar
        probabilities={result.probabilities}
        categoryOrder={CATEGORY_ORDER}
        accentClass={accentClass}
      />
      {explain && model.explainable && !explain.tokens && (
        <button
          type="button"
          className="explain-button"
          onClick={explain.onExplain}
          disabled={explain.loading || cantAfford}
          title={cantAfford ? `Needs ${explainCost} credits` : undefined}
        >
          {explain.loading
            ? "Explaining..."
            : `Explain${explainCost != null && explain.credits !== null ? ` (${explainCost} credit${explainCost === 1 ? "" : "s"})` : ""}`}
        </button>
      )}
      {explain && !model.explainable && (
        <p className="explain-unavailable">Explanation isn't available for this model.</p>
      )}
      {explain?.tokens && <TokenHighlight tokens={explain.tokens} />}
    </div>
  );
}
