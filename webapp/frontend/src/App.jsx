import { useCallback, useEffect, useState } from "react";
import TextInputForm from "./components/TextInputForm";
import MultiLineForm from "./components/MultiLineForm";
import CsvUploadForm from "./components/CsvUploadForm";
import ResultsSingle from "./components/ResultsSingle";
import SummaryTable from "./components/SummaryTable";
import ModelSelector from "./components/ModelSelector";
import QuotaBadge from "./components/QuotaBadge";
import {
  predictText,
  explainText,
  predictBatch,
  buildCsvBlob,
  mapBatchRowsToSummary,
  downloadCsv,
  fetchModels,
  fetchQuota,
} from "./api";
import { DEFAULT_SELECTED_KEYS } from "./constants";
import "./styles.css";

function App() {
  const [mode, setMode] = useState("text");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [singleResult, setSingleResult] = useState(null);
  const [summaryRows, setSummaryRows] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [limits, setLimits] = useState({});
  const [selectedKeys, setSelectedKeys] = useState(DEFAULT_SELECTED_KEYS);
  const [quota, setQuota] = useState(null);
  // Per-model explanations for the current single-text result.
  const [explanations, setExplanations] = useState({});
  const [explainingKey, setExplainingKey] = useState(null);

  const refreshQuota = useCallback(() => {
    fetchQuota()
      .then(setQuota)
      .catch(() => {}); // the badge is informational; the backend still enforces limits
  }, []);

  useEffect(() => {
    fetchModels()
      .then(({ models, limits: serverLimits }) => {
        setAvailableModels(models);
        setLimits(serverLimits ?? {});
        setSelectedKeys((prev) => prev.filter((k) => models.some((m) => m.key === k && m.loaded)));
      })
      .catch((err) => setError(err.message));
    refreshQuota();
  }, [refreshQuota]);

  const selectedModels = availableModels.filter((m) => selectedKeys.includes(m.key));
  const costPerText = selectedModels.reduce((sum, m) => sum + (m.cost?.predict ?? 0), 0);
  // null = no limits (local dev); otherwise the most this visitor can spend now.
  const credits = quota?.enabled ? Math.min(quota.remaining, quota.global_remaining) : null;
  const formProps = { loading, costPerText, credits, noModels: selectedKeys.length === 0 };

  function switchMode(nextMode) {
    setMode(nextMode);
    setSingleResult(null);
    setSummaryRows(null);
    setExplanations({});
    setError(null);
  }

  // Every response carries the visitor's updated quota; a 429 error carries it too.
  function handleError(err) {
    setError(err.message);
    if (err.quota) setQuota(err.quota);
  }

  async function handleTextSubmit(text) {
    setLoading(true);
    setError(null);
    setSingleResult(null);
    setExplanations({});
    try {
      const data = await predictText(text, selectedKeys);
      setSingleResult(data);
      if (data.quota) setQuota(data.quota);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleExplain(modelKey) {
    setExplainingKey(modelKey);
    setError(null);
    try {
      const data = await explainText(singleResult.input_text, [modelKey]);
      setExplanations((prev) => ({ ...prev, [modelKey]: data.results[modelKey]?.tokens ?? [] }));
      if (data.quota) setQuota(data.quota);
    } catch (err) {
      handleError(err);
    } finally {
      setExplainingKey(null);
    }
  }

  async function handleBatchSubmit(fileOrBlob) {
    setLoading(true);
    setError(null);
    setSummaryRows(null);
    try {
      const data = await predictBatch(fileOrBlob, selectedKeys);
      setSummaryRows(mapBatchRowsToSummary(data));
      if (data.quota) setQuota(data.quota);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  function handleLinesSubmit(lines) {
    handleBatchSubmit(buildCsvBlob(lines));
  }

  const explainFor = (modelKey) => ({
    onExplain: () => handleExplain(modelKey),
    tokens: explanations[modelKey],
    loading: explainingKey === modelKey,
    credits,
  });

  return (
    <div className="app">
      <header>
        <div className="header-row">
          <h1>Text Categorization: Model Comparison</h1>
          <QuotaBadge quota={quota} onExpire={refreshQuota} />
        </div>
        <p className="subtitle">
          Compare trained models (SVM, LSTM, BERT, Zero-Shot) on the same input, side by side. Only the
          models you select are run.
        </p>
      </header>

      <ModelSelector
        availableModels={availableModels}
        selectedKeys={selectedKeys}
        onChange={setSelectedKeys}
        showCosts={credits !== null}
      />

      <div className="mode-toggle">
        <button className={mode === "text" ? "active" : ""} onClick={() => switchMode("text")}>
          Single Text
        </button>
        <button className={mode === "lines" ? "active" : ""} onClick={() => switchMode("lines")}>
          Multiple Lines
        </button>
        <button className={mode === "csv" ? "active" : ""} onClick={() => switchMode("csv")}>
          CSV Upload
        </button>
      </div>

      {mode === "text" && (
        <TextInputForm onSubmit={handleTextSubmit} maxChars={limits.max_text_chars} {...formProps} />
      )}
      {mode === "lines" && (
        <MultiLineForm onSubmit={handleLinesSubmit} maxRows={limits.batch_max_rows} {...formProps} />
      )}
      {mode === "csv" && (
        <CsvUploadForm onSubmit={handleBatchSubmit} maxRows={limits.batch_max_rows} {...formProps} />
      )}

      {error && <div className="error-banner">{error}</div>}

      {mode === "text" && singleResult && (
        <ResultsSingle data={singleResult} models={availableModels} explainFor={explainFor} />
      )}
      {mode !== "text" && summaryRows && (
        <SummaryTable
          rows={summaryRows}
          models={availableModels.filter((m) => summaryRows[0] && summaryRows[0].results[m.key])}
          onDownload={() =>
            downloadCsv(
              `${mode}-predictions.csv`,
              summaryRows,
              availableModels.filter((m) => summaryRows[0] && summaryRows[0].results[m.key])
            )
          }
        />
      )}
    </div>
  );
}

export default App;
