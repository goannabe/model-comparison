import ConfidenceBar from "./ConfidenceBar";
import TokenHighlight from "./TokenHighlight";
import { CATEGORY_ORDER, MODEL_ACCENT_CLASS } from "../constants";

export default function ModelCard({ model, result }) {
  const accentClass = MODEL_ACCENT_CLASS[model.family] || "";
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
      <TokenHighlight tokens={result.tokens} />
    </div>
  );
}
