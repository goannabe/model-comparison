import { FAMILY_LABELS } from "../constants";

export default function ModelSelector({ availableModels, selectedKeys, onChange }) {
  const families = [];
  for (const m of availableModels) {
    if (!families.includes(m.family)) families.push(m.family);
  }

  function toggle(key) {
    const next = new Set(selectedKeys);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(Array.from(next));
  }

  function toggleFamily(family, models) {
    const keys = models.map((m) => m.key);
    const allSelected = keys.every((k) => selectedKeys.includes(k));
    const next = new Set(selectedKeys);
    if (allSelected) keys.forEach((k) => next.delete(k));
    else keys.forEach((k) => next.add(k));
    onChange(Array.from(next));
  }

  return (
    <div className="model-selector">
      {families.map((family) => {
        const models = availableModels.filter((m) => m.family === family);
        const allSelected = models.every((m) => selectedKeys.includes(m.key));
        return (
          <div className="model-selector-family" key={family}>
            <label className="model-selector-family-label">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => toggleFamily(family, models)}
              />
              <strong>{FAMILY_LABELS[family] || family}</strong>
            </label>
            <div className="model-selector-options">
              {models.map((m) => (
                <label className="model-selector-option" key={m.key}>
                  <input
                    type="checkbox"
                    checked={selectedKeys.includes(m.key)}
                    disabled={!m.loaded}
                    onChange={() => toggle(m.key)}
                  />
                  {m.label}
                  {!m.loaded && <span className="model-selector-error"> (failed to load)</span>}
                </label>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
