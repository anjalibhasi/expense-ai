import os
import pickle


def _asset_path(filename):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', filename))


def load_model():
    model = pickle.load(open(_asset_path('model.pkl'), 'rb'))
    vectorizer = pickle.load(open(_asset_path('vectorizer.pkl'), 'rb'))
    return model, vectorizer


def ai_predict(desc, model, vectorizer):
    if not desc or not desc.strip():
        return 'Other', 0
    X = vectorizer.transform([desc])
    return model.predict(X)[0], round(model.predict_proba(X).max() * 100)
