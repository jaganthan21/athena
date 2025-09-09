from pymongo import MongoClient
import pandas as pd
import os

# --- CONFIG ---
MONGO_URI="mongodb+srv://aig_user1:aig_user1@marscluster.xpeduww.mongodb.net/?retryWrites=true&w=majority&appName=marsCluster"
OUTPUT_DIR = "mongo_exports"

# Create output directory if not exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Connect to Mongo
client = MongoClient(MONGO_URI)

# List all databases
db_names = client.list_database_names()

print(f"Found databases: {db_names}")

for db_name in db_names:
    # Skip internal databases unless you want them
    if db_name in ("admin", "local", "config"):
        continue
    
    db = client[db_name]
    collections = db.list_collection_names()
    
    print(f"\n📂 Database: {db_name} | Collections: {collections}")
    
    for coll_name in collections:
        print(f"   → Exporting {coll_name}...")
        collection = db[coll_name]
        
        # Fetch all documents
        docs = list(collection.find())
        
        if not docs:
            print(f"(Skipping empty collection)")
            continue
        
        # Convert to DataFrame
        df = pd.DataFrame(docs)
        
        # Drop MongoDB internal `_id` if not needed
        if "_id" in df.columns:
            df.drop(columns=["_id"], inplace=True)
        
        # Save to CSV
        db_dir = os.path.join(OUTPUT_DIR, db_name)
        os.makedirs(db_dir, exist_ok=True)
        output_file = os.path.join(db_dir, f"{coll_name}.csv")
        
        df.to_csv(output_file, index=False, encoding="utf-8")
        print(f"     ✔ Saved {output_file}")

print("\n✅ Export complete.")
