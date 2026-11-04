import { useState } from "react";

export default function TextInputForm({ onSubmit, loading }) {
  const [text, setText] = useState("");

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
      <button type="submit" disabled={loading || !text.trim()}>
        {loading ? "Predicting..." : "Predict"}
      </button>
    </form>
  );
}
