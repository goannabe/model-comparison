import { useRef, useState } from "react";

export default function CsvUploadForm({ onSubmit, loading }) {
  const [file, setFile] = useState(null);
  const [rowCount, setRowCount] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  async function selectFile(nextFile) {
    if (!nextFile) {
      setFile(null);
      setRowCount(null);
      return;
    }
    setFile(nextFile);
    const text = await nextFile.text();
    const nonEmptyLines = text.split("\n").filter((l) => l.trim().length > 0);
    setRowCount(Math.max(0, nonEmptyLines.length - 1));
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) selectFile(dropped);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (file) onSubmit(file);
  }

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <p className="hint">CSV must have a "text" column (max 200 rows, 5MB).</p>
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <svg
          className="dropzone-icon"
          viewBox="0 0 24 24"
          width="32"
          height="32"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M12 16V4M12 4l-4 4M12 4l4 4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p>Drag a CSV here or click to browse</p>
        <button
          type="button"
          className="choose-file-button"
          onClick={(e) => {
            e.stopPropagation();
            inputRef.current?.click();
          }}
        >
          Choose file
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          hidden
          onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
        />
      </div>
      {file && (
        <p className="hint">
          Selected: {file.name} ({rowCount} row{rowCount === 1 ? "" : "s"} detected)
        </p>
      )}
      <button type="submit" disabled={loading || !file}>
        {loading ? "Processing..." : "Run batch prediction"}
      </button>
    </form>
  );
}
