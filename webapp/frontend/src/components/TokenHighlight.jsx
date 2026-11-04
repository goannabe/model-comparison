function scoreToStyle(score) {
  const clamped = Math.max(-1, Math.min(1, score));
  const alpha = Math.abs(clamped).toFixed(2);
  const color = clamped >= 0 ? `rgba(34, 197, 94, ${alpha})` : `rgba(239, 68, 68, ${alpha})`;
  return { backgroundColor: color };
}

export default function TokenHighlight({ tokens }) {
  if (!tokens || tokens.length === 0) {
    return null;
  }

  return (
    <div className="token-highlight">
      <p className="token-highlight-label">Why this prediction:</p>
      <div className="token-highlight-tokens">
        {tokens.map((t, i) => (
          <span key={i} className="token-chip" style={scoreToStyle(t.score)} title={t.score.toFixed(2)}>
            {t.token}
          </span>
        ))}
      </div>
    </div>
  );
}
