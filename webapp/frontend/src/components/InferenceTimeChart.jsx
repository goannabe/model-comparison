export default function InferenceTimeChart({ timings, models }) {
  const values = models.map((m) => timings[m.key]).filter((v) => v > 0);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const useLogScale = min > 0 && max / min >= 10;

  function barWidthPct(ms) {
    if (ms <= 0) return 0;
    if (!useLogScale) return (ms / max) * 100;
    const logMin = Math.log10(Math.max(min, 0.01));
    const logMax = Math.log10(max);
    const logVal = Math.log10(Math.max(ms, 0.01));
    const range = logMax - logMin || 1;
    return Math.max(4, ((logVal - logMin) / range) * 100);
  }

  return (
    <div className="inference-chart">
      <h4>
        Inference time comparison {useLogScale && <span className="chart-scale-note">(log scale)</span>}
      </h4>
      {models.map((m) => (
        <div className="inference-row" key={m.key}>
          <span className="inference-model-label">{m.label}</span>
          <div className="inference-track">
            <div
              className={`inference-fill inference-fill-${m.family}`}
              style={{ width: `${barWidthPct(timings[m.key])}%` }}
            />
          </div>
          <span className="inference-ms-label">{timings[m.key].toFixed(1)} ms</span>
        </div>
      ))}
    </div>
  );
}
