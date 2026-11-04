// Base models pre-selected on first load, before /api/models/ has told us
// what's actually available. Everything else (variants, zero-shot) starts
// unchecked so the default view matches the original 3-model comparison.
export const DEFAULT_SELECTED_KEYS = ["svm", "lstm", "bert"];

export const FAMILY_LABELS = {
  svm: "SVM",
  lstm: "LSTM",
  bert: "BERT",
  zeroshot: "Zero-Shot",
};

export const MODEL_ACCENT_CLASS = {
  svm: "accent-svm",
  lstm: "accent-lstm",
  bert: "accent-bert",
  zeroshot: "accent-zeroshot",
};

export const CATEGORY_ORDER = [
  "Business",
  "Entertainment",
  "Health",
  "Politics",
  "Science",
  "Sports",
  "Technology",
  "World",
];
