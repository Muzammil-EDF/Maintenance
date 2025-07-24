import pandas as pd
from sqlalchemy import create_engine, text

# PostgreSQL DB URL
db_url = "postgresql://postgres:wirpfNiJcMFNYPFSNFTMTwRDaekFLvos@metro.proxy.rlwy.net:12041/railway"
engine = create_engine(db_url)

# Step 1: Delete old data
with engine.connect() as conn:
    conn.execute(text("DELETE FROM todo"))
    conn.commit()
    print("All rows deleted from 'todo' table.")

# Step 2: Load CSV
df = pd.read_csv(r'C:\Users\muhammadmuzammil\Desktop\Master File.csv')

# Step 3: Rename columns to match DB
df.columns = [col.strip().lower() for col in df.columns]  # lowercase & strip spaces
df.rename(columns={
    "category": "category",
    "desc": "desc",
    "tag": "tag",
    "unit": "unit",
    "building": "building",
    "floor": "floor",
    "serial": "serial",
    "date": "date",
    "home": "home",
    "status": "status",
    "brand": "brand",
    "model": "model",
    "sno": "sno"
}, inplace=True)

# Step 4: Drop rows where required fields like sno are missing
df.dropna(subset=["sno"], inplace=True)

# Step 5: Add missing columns with defaults
df['pm_date'] = None
df['pm_status'] = 'Pending'
df['checklist'] = None

# Step 6: Reorder columns
df = df[[
    "sno", "category", "desc", "tag", "unit", "building", "floor", "serial", "date",
    "home", "status", "brand", "model", "pm_date", "pm_status", "checklist"
]]

# Optional: Fix `date` column format if needed
# df['date'] = pd.to_datetime(df['date'], errors='coerce')

# Step 7: Upload
df.to_sql("todo", engine, if_exists='append', index=False)
print("Upload complete. Rows inserted:", len(df))
