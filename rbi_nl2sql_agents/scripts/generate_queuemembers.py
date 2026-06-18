import os
import pandas as pd
import random

def generate_queuemembers():
    # Columns in CRMNEXT.queuemembers table
    columns = [
        "OWNERID", "QUEUEID", "QUEUETYPE", "MEMBERID", 
        "LASTMODIFIEDBYTYPE", "ADDEDBY", "SHOWQUEUEMEMBERS", "IPADDRESS"
    ]

    # First 14 rows from the screenshot image
    first_14 = [
        {"OWNERID": 721, "QUEUEID": 5349, "QUEUETYPE": 2, "MEMBERID": 5918, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 11728, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5379, "QUEUETYPE": 2, "MEMBERID": 12674, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 11551, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5333, "QUEUETYPE": 2, "MEMBERID": 14123, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 13023, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5359, "QUEUETYPE": 2, "MEMBERID": 14100, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 5650, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5349, "QUEUETYPE": 2, "MEMBERID": 11099, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 5475, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5383, "QUEUETYPE": 2, "MEMBERID": 5635, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 11479, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5369, "QUEUETYPE": 2, "MEMBERID": 6011, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 5635, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5383, "QUEUETYPE": 2, "MEMBERID": 5628, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 11479, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5369, "QUEUETYPE": 2, "MEMBERID": 7127, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 5477, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5347, "QUEUETYPE": 2, "MEMBERID": 15750, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 5475, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5359, "QUEUETYPE": 2, "MEMBERID": 5814, "LASTMODIFIEDBYTYPE": -1, "ADDEDBY": 5826, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5350, "QUEUETYPE": 2, "MEMBERID": 5400, "LASTMODIFIEDBYTYPE": 0, "ADDEDBY": 1, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5352, "QUEUETYPE": 2, "MEMBERID": 5393, "LASTMODIFIEDBYTYPE": 0, "ADDEDBY": 1, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None},
        {"OWNERID": 721, "QUEUEID": 5353, "QUEUETYPE": 2, "MEMBERID": 5393, "LASTMODIFIEDBYTYPE": 0, "ADDEDBY": 1, "SHOWQUEUEMEMBERS": 0, "IPADDRESS": None}
    ]

    # Read queue.csv to get valid queue IDs and their types
    queue_file = "project_data/cms/queue.csv"
    if not os.path.exists(queue_file):
        raise FileNotFoundError(f"Could not find queue.csv file at {queue_file}. Please run generate_queue.py first.")
    
    queue_df = pd.read_csv(queue_file)
    queue_type_map = dict(zip(queue_df["QUEUEID"], queue_df["QUEUETYPE"]))

    # Seed random for reproducibility
    random.seed(42)

    # Establish pools of values for realistic data relationship
    # Pool of 100 distinct member IDs (users)
    member_pool = [random.randint(5000, 16000) for _ in range(100)]
    # Pool of addedby IDs
    addedby_pool = [1, 5475, 5477, 5635, 11479, 11551, 11728, 13023, 5650, 5826]

    data = first_14.copy()
    
    # We want 500 rows in total, so we need 486 more rows.
    # Keep track of generated (QUEUEID, MEMBERID) pairs to avoid duplicates if possible, or just generate realistically
    seen_pairs = set((row["QUEUEID"], row["MEMBERID"]) for row in data)
    
    attempts = 0
    while len(data) < 500 and attempts < 10000:
        attempts += 1
        queue_id = random.choice(list(queue_type_map.keys()))
        queue_type = queue_type_map[queue_id]
        member_id = random.choice(member_pool)
        
        pair = (queue_id, member_id)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            
            row = {
                "OWNERID": 721,
                "QUEUEID": queue_id,
                "QUEUETYPE": queue_type,
                "MEMBERID": member_id,
                "LASTMODIFIEDBYTYPE": random.choice([-1, 0]),
                "ADDEDBY": random.choice(addedby_pool),
                "SHOWQUEUEMEMBERS": 0 if random.random() < 0.95 else 1,
                "IPADDRESS": None
            }
            data.append(row)

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Reorder columns to match original DB schema
    df = df[columns]

    # Write to Excel and CSV files in cms folder
    os.makedirs("project_data/cms", exist_ok=True)
    excel_path = "project_data/cms/queuemembers.xlsx"
    csv_path = "project_data/cms/queuemembers.csv"
    
    df.to_excel(excel_path, index=False)
    df.to_csv(csv_path, index=False)

    print(f"QueueMembers dataset generation complete!")
    print(f"Generated {len(df)} rows.")
    print(f"Saved to: {excel_path} and {csv_path}")

if __name__ == "__main__":
    generate_queuemembers()
