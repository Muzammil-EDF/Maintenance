import pandas as pd
from sqlalchemy import create_engine, text

# DB connection
db_url = "postgresql://postgres:wirpfNiJcMFNYPFSNFTMTwRDaekFLvos@metro.proxy.rlwy.net:12041/railway"
engine = create_engine(db_url)

# Delete existing data
with engine.connect() as conn:
    conn.execute(text("DELETE FROM todo"))
    conn.commit()
    print("All rows deleted from 'todo' table.")

# Load CSV
df = pd.read_csv(r'C:\Users\obeya.ytm7\Desktop\Master_File_Central_Engineering.csv')

# Clean column names (remove spaces, lowercase)
df.columns = [col.strip().lower() for col in df.columns]
print("CSV columns:", df.columns.tolist())  # Debug print

# Rename columns if needed (adjust as per your actual CSV)
df.rename(columns={
    's.no': 'sno',
    'description': 'desc',
    # Add more renames if necessary
}, inplace=True)

# Add missing columns
df['pm_date'] = None
df['pm_status'] = 'Pending'
df['checklist'] = None

# Reorder
expected_cols = [
    "sno", "category", "desc", "tag", "unit", "building", "floor", "serial", "date",
    "home", "status", "brand", "model", "pm_date", "pm_status", "checklist"
]
# Keep only available columns to avoid KeyError
df = df[[col for col in expected_cols if col in df.columns]]

# Upload
df.to_sql("todo", engine, if_exists='append', index=False)
print("Re-upload completed successfully.")
