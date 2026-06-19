import os
import pandas as pd

def generate_lookup():
    # Define columns matching the CRMNEXT.mv_lookup_origin table schema
    columns = ["LOOKUPID", "GROUPKEY", "NAME"]

    # 9 rows from the screenshot image
    data = [
        {"LOOKUPID": 0, "GROUPKEY": 74, "NAME": None},
        {"LOOKUPID": 1, "GROUPKEY": 74, "NAME": "Email"},
        {"LOOKUPID": 2, "GROUPKEY": 74, "NAME": "Complaint Portal"},
        {"LOOKUPID": 3, "GROUPKEY": 74, "NAME": "Physical Letter"},
        {"LOOKUPID": 4, "GROUPKEY": 74, "NAME": "CPGRAMS"},
        {"LOOKUPID": 7, "GROUPKEY": 74, "NAME": "RIA"},
        {"LOOKUPID": 8, "GROUPKEY": 74, "NAME": "Legal"},
        {"LOOKUPID": 9, "GROUPKEY": 74, "NAME": "FRC Portal"},
        {"LOOKUPID": 10, "GROUPKEY": 74, "NAME": "Sub Judice Portal"}
    ]

    # Convert to DataFrame
    df = pd.DataFrame(data)
    df = df[columns]

    # Write to Excel and CSV files in cms folder
    os.makedirs("project_data/cms", exist_ok=True)
    excel_path = "project_data/cms/mv_lookup_origin.xlsx"
    csv_path = "project_data/cms/mv_lookup_origin.csv"
    
    df.to_excel(excel_path, index=False)
    df.to_csv(csv_path, index=False)

    print(f"MV Lookup Origin dataset generation complete!")
    print(f"Generated {len(df)} rows.")
    print(f"Saved to: {excel_path} and {csv_path}")

if __name__ == "__main__":
    generate_lookup()
