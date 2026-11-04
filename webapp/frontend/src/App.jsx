import { useEffect, useState } from "react";
import TextInputForm from "./components/TextInputForm";
import MultiLineForm from "./components/MultiLineForm";
import CsvUploadForm from "./components/CsvUploadForm";
import ResultsSingle from "./components/ResultsSingle";
import SummaryTable from "./components/SummaryTable";
import ModelSelector from "./components/ModelSelector";
import {
  predictWithExplanation,
  predictBatch,
  buildCsvBlob,
  mapBatchRowsToSummary,
  downloadCsv,
  fetchModels,
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
  const [selectedKeys, setSelectedKeys] = useState(DEFAULT_SELECTED_KEYS);

  useEffect(() => {
    fetchModels()
      .then((models) => {
        setAvailableModels(models);
        setSelectedKeys((prev) => prev.filter((k) => models.some((m) => m.key === k && m.loaded)));
      })
      .catch((err) => setError(err.message));
  }, []);

  const selectedModels = availableModels.filter((m) => selectedKeys.includes(m.key));

  function switchMode(nextMode) {
    setMode(nextMode);
    setSingleResult(null);
    setSummaryRows(null);
    setError(null);
  }

  async function handleTextSubmit(text) {
    setLoading(true);
    setError(null);
    setSingleResult(null);
    try {
      setSingleResult(await predictWithExplanation(text));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleBatchSubmit(fileOrBlob) {
    setLoading(true);
    setError(null);
    setSummaryRows(null);
    try {
      const data = await predictBatch(fileOrBlob);
      setSummaryRows(mapBatchRowsToSummary(data));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleLinesSubmit(lines) {
    handleBatchSubmit(buildCsvBlob(lines));
  }

  return (
    <div className="app">
      <header>
        <h1>Text Categorization: Model Comparison</h1>
        <p className="subtitle">
          Compare trained models and variants (SVM, LSTM, BERT, Zero-Shot) on the same input, side by side.
        </p>
      </header>

      <ModelSelector
        availableModels={availableModels}
        selectedKeys={selectedKeys}
        onChange={setSelectedKeys}
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

      {mode === "text" && <TextInputForm onSubmit={handleTextSubmit} loading={loading} />}
      {mode === "lines" && <MultiLineForm onSubmit={handleLinesSubmit} loading={loading} />}
      {mode === "csv" && <CsvUploadForm onSubmit={handleBatchSubmit} loading={loading} />}

      {error && <div className="error-banner">{error}</div>}

      {mode === "text" && singleResult && (
        <ResultsSingle data={singleResult} models={selectedModels} />
      )}
      {mode !== "text" && summaryRows && (
        <SummaryTable
          rows={summaryRows}
          models={selectedModels}
          onDownload={() => downloadCsv(`${mode}-predictions.csv`, summaryRows, selectedModels)}
        />
      )}
    </div>
  );
}

export default App;
