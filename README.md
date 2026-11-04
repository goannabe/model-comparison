# Model Comparison: Text Classification

A comparative study of four model families for news-topic text classification,
plus a web app to compare their predictions side by side:

| Family | Model |
|---|---|
| **SVM** | Linear SVM over TF-IDF features (scikit-learn) |
| **LSTM** | Bidirectional LSTM trained from scratch (Keras) |
| **BERT** | Fine-tuned `bert-base-uncased` (Hugging Face Transformers) |
| **Zero-shot** | `facebook/bart-large-mnli`, no fine-tuning |

## Repository structure

```
.
├── models/
│   └── training/          Jupyter notebooks: data collection, splits, training, evaluation
│       ├── DataCollection.ipynb          Downloads + merges the source datasets, cleans text, maps labels
│       ├── ModelPrep.ipynb               Builds the final dataset and train/val/test splits
│       ├── LOSO_Splits.ipynb             Leave-one-source-out splits (cross-domain generalisation)
│       ├── NoiseRobustness_Splits.ipynb  Splits with 10% label noise (robustness test)
│       ├── svm/        SVM_a (baseline), SVM_b (grid-search tuned), SVM_LOSO, SVM_Noise
│       ├── lstm/       LSTM_a (baseline), LSTM_b-e (dropout / embedding / LR / units variants), LSTM_LOSO, LSTM_Noise
│       ├── bert/       BERT_a (baseline), BERT_b (LR 3e-5), BERT_c (DistilBERT), BERT_LOSO, BERT_Noise
│       └── zeroshot/   ZeroShot_a (bare category names), ZeroShot_b (descriptive labels + news-specific template)
├── results/               Metrics (JSON) and confusion matrices (PNG) for every run
│   ├── svm/  lstm/  bert/  zeroshot/
│   └── */loso/            Leave-one-source-out results
├── webapp/
│   ├── backend/           Django + DRF API that loads the trained models and serves predictions/explanations
│   ├── frontend/          React + Vite UI for comparing models side by side (single text or CSV batch)
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
└── docker-compose.yml     Runs backend + frontend together
```

In each family, version **a** is the baseline; later letters are hyperparameter or
architecture variants. Each notebook's first cell describes exactly what changed.

## Model weights and data

Trained weights (~1.4 GB) and the processed dataset are too large for GitHub and
are not in this repository. The weights are published on Hugging Face:
[goannabe/model-comparison-weights](https://huggingface.co/goannabe/model-comparison-weights).

Download them into `models/` (the backend reads `models/weights/`):

```bash
pip install -U huggingface_hub
hf download goannabe/model-comparison-weights --local-dir models
```

The zero-shot model (`facebook/bart-large-mnli`) is downloaded automatically on first use.

## Running the web app

**With Docker** (downloads the weights during the build):

```bash
docker compose up --build
# frontend: http://localhost:5173   backend: http://localhost:8000
```

**Locally**, after downloading the weights:

```bash
# Backend
cd webapp/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # http://localhost:8000

# Frontend (in another terminal)
cd webapp/frontend
npm install
npm run dev                       # http://localhost:5173
```

## Training notebooks

The notebooks under `models/training/` were run in order:
`DataCollection` → `ModelPrep` → (`LOSO_Splits`, `NoiseRobustness_Splits`) → the per-family
notebooks. They write weights to `models/weights/` and metrics to `results/`.
Re-running them needs the processed data in `models/data/`, which is not included here;
`DataCollection.ipynb` rebuilds it from the public source datasets on Hugging Face.
