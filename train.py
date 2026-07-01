import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import pickle

df = pd.read_csv('train.csv')
expected_cols = ['Transaction Description', 'Category', 'Type']
if not all(col in df.columns for col in expected_cols):
    raise ValueError(f"train.csv must contain columns: {expected_cols}. Found: {list(df.columns)}")

# Only use expense transactions for category training
expense_df = df[df['Type'].astype(str).str.strip().str.lower() == 'expense']
if expense_df.empty:
    raise ValueError('train.csv must contain at least one expense row in the Type column.')

df = expense_df[['Transaction Description', 'Category']].dropna()
df = df.rename(columns={'Transaction Description': 'desc', 'Category': 'category'})

category_map = {
    'Food & Drink': 'Food',
    'Food/Dining': 'Food',
    'Utilities': 'Bills',
    'Bills & Utilities': 'Bills',
    'Rent': 'Bills',
    'Travel': 'Transport',
    'Gas/Automotive': 'Transport',
    'Health & Fitness': 'Health',
    'Entertainment': 'Entertainment',
    'Shopping': 'Shopping',
    'Other': 'Other',
    'Investment': 'Other',
    'Salary': 'Other'
}
df['category'] = df['category'].map(category_map)
df = df.dropna().head(5000)

indian = [["zepto", "Groceries"], ["swiggy", "Food"], ["metro recharge", "Transport"],
          ["bescom bill", "Bills"], ["bigbasket", "Groceries"], ["zomato", "Food"]]
df = pd.concat([df, pd.DataFrame(indian, columns=['desc', 'category'])])

vectorizer = TfidfVectorizer(stop_words='english')
X = vectorizer.fit_transform(df['desc'])
model = MultinomialNB()
model.fit(X, df['category'])

pickle.dump(model, open('model.pkl', 'wb'))
pickle.dump(vectorizer, open('vectorizer.pkl', 'wb'))
print("AI ready!")