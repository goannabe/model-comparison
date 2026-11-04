export default function ConfidenceBar({ probabilities, categoryOrder, accentClass }) {
  const scoreByLabel = new Map(probabilities.map((p) => [p.label, p.score]));
  const ordered = (categoryOrder || probabilities.map((p) => p.label)).map((label) => ({
    label,
    score: scoreByLabel.get(label) ?? 0,
  }));

  return (
    <ul className="confidence-list">
      {ordered.map(({ label, score }) => (
        <li key={label} className="confidence-row">
          <span className="confidence-label">{label}</span>
          <div className="confidence-track">
            <div
              className={`confidence-fill ${accentClass || ""}`}
              style={{ width: `${score * 100}%` }}
            />
          </div>
          <span className="confidence-score">{(score * 100).toFixed(0)}%</span>
        </li>
      ))}
    </ul>
  );
}
