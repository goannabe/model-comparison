import ModelCard from "./ModelCard";
import InferenceTimeChart from "./InferenceTimeChart";

// `explainFor(modelKey)` (optional) returns the per-card explain props; only
// single-text results pass it, so batch rows show no Explain buttons.
export default function PredictionDetail({ results, totalMs, models, explainFor }) {
  const shown = models.filter((m) => results[m.key]);
  const labels = shown.map((m) => results[m.key].predicted_label);
  const disagree = new Set(labels).size > 1;
  const timings = Object.fromEntries(shown.map((m) => [m.key, results[m.key].inference_ms]));

  return (
    <div className="prediction-detail">
      {disagree && <div className="disagree-banner">Models disagree on this input</div>}
      <div className="model-columns">
        {shown.map((m) => (
          <ModelCard key={m.key} model={m} result={results[m.key]} explain={explainFor?.(m.key)} />
        ))}
      </div>
      <InferenceTimeChart timings={timings} models={shown} />
      {typeof totalMs === "number" && (
        <p className="total-time">Total round-trip: {totalMs.toFixed(1)} ms</p>
      )}
    </div>
  );
}
