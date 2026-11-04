import PredictionDetail from "./PredictionDetail";

export default function ResultsSingle({ data, models }) {
  return <PredictionDetail results={data.results} totalMs={data.total_ms} models={models} />;
}
