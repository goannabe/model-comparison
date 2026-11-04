import { useState } from "react";

export default function MultiLineForm({ onSubmit, loading }) {
  const [text, setText] = useState("");
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

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
      <p className="hint">{lines.length} line{lines.length === 1 ? "" : "s"} detected</p>
      <button type="submit" disabled={loading || lines.length === 0}>
        {loading ? "Predicting..." : "Predict all"}
      </button>
    </form>
  );
}
