import { Fragment, useState } from "react";
import PredictionDetail from "./PredictionDetail";

export default function SummaryTable({ rows, onDownload, models }) {
  const [expandedId, setExpandedId] = useState(null);

  return (
    <div className="summary-table-wrap">
      <div className="summary-toolbar">
        <button className="download-button" onClick={onDownload}>
          Download as CSV
        </button>
      </div>
      <table className="summary-table">
        <thead>
          <tr>
            <th></th>
            <th>#</th>
            <th>Text</th>
            {models.map((m) => (
              <th key={m.key}>{m.label}</th>
            ))}
            <th>Agreement</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const shown = models.filter((m) => row.results[m.key]);
            const labels = shown.map((m) => row.results[m.key].predicted_label);
            const disagree = new Set(labels).size > 1;
            const isExpanded = expandedId === row.id;
            return (
              <Fragment key={row.id}>
                <tr
                  className={disagree ? "row-disagree" : ""}
                  onClick={() => setExpandedId(isExpanded ? null : row.id)}
                >
                  <td>
                    <span className={`chevron ${isExpanded ? "chevron-open" : ""}`}>&#9656;</span>
                  </td>
                  <td>{row.id}</td>
                  <td className="text-preview">{row.label}</td>
                  {shown.map((m) => (
                    <td key={m.key}>
                      {row.results[m.key].predicted_label}
                      <span className="cell-ms"> ({row.results[m.key].inference_ms.toFixed(1)}ms)</span>
                    </td>
                  ))}
                  <td>
                    <span className={`badge ${disagree ? "badge-disagree" : "badge-agree"}`}>
                      {disagree ? "Disagree" : "Agree"}
                    </span>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="row-detail">
                    <td colSpan={4 + shown.length}>
                      <PredictionDetail results={row.results} models={models} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
