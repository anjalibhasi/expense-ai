# FinAI - Expense Tracker

Personal expense tracker with AI category prediction.

Quick start

1. Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

2. Train the model (optional):

```bash
python train.py
```

3. Run the app:

```bash
python app.py
```

Notes

- `model.pkl`, `vectorizer.pkl`, and `expenses.db` are ignored by `.gitignore`.
- If you need to store models in Git, use Git LFS for large files.
