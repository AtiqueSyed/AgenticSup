import os
import pandas as pd

def generate_regions():
    # Columns in CRMNEXT.regions table
    columns = [
        "OWNERID", "REGIONID", "PARENTREGIONID", "ISPARENT", "NAME", 
        "DESCRIPTION", "CREATEDBY", "CREATEDON", "LASTMODIFIEDBY", "LASTMODIFIEDON", 
        "ZIPCODE", "CATEGORYTYPE", "CONTINENTID", "CONTINENTNAME", "ZONEID", 
        "ZONENAME", "AREAID", "AREANAME", "CLUSTERID", "CLUSTERNAME", 
        "BRANCHID", "BRANCHNAME", "LOCATIONID", "LOCATIONNAME", "PROCESSID", 
        "PROCESSVERSION", "LAYOUTID"
    ]

    # First 19 rows from the screenshot image
    first_19 = [
        {"OWNERID": 721, "REGIONID": 5347, "PARENTREGIONID": 0, "ISPARENT": 1, "NAME": "Southern Zone", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "29-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 4},
        {"OWNERID": 721, "REGIONID": 5348, "PARENTREGIONID": 0, "ISPARENT": 1, "NAME": "Eastern Zone", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "29-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 4},
        {"OWNERID": 721, "REGIONID": 5353, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "BO Raipur", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 5475, "LASTMODIFIEDON": "22-JUN-20", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5352, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "BO Bhopal", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 5475, "LASTMODIFIEDON": "22-JUN-20", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5358, "PARENTREGIONID": 5347, "ISPARENT": 0, "NAME": "NBFC Chennai", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "22-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5365, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "CEPD Mumbai", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "03-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "22-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5372, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "CEPC Ahmedabad", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5375, "PARENTREGIONID": 5347, "ISPARENT": 0, "NAME": "CEPC Bengaluru", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5377, "PARENTREGIONID": 5348, "ISPARENT": 0, "NAME": "CEPC-Bhopal", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5385, "PARENTREGIONID": 5348, "ISPARENT": 0, "NAME": "CEPC-Imphal", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5387, "PARENTREGIONID": 5349, "ISPARENT": 0, "NAME": "CEPC-Jammu", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5389, "PARENTREGIONID": 5347, "ISPARENT": 0, "NAME": "CEPC-Kochi", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5409, "PARENTREGIONID": 5349, "ISPARENT": 0, "NAME": "BO Dehradun", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "31-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "31-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5393, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "CEPC-Nagpur", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5395, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "CEPC-Panaji", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "30-JAN-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "30-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5425, "PARENTREGIONID": 5348, "ISPARENT": 0, "NAME": "ODT-Patna", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "04-FEB-19", "LASTMODIFIEDBY": 5475, "LASTMODIFIEDON": "22-JUN-20", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5426, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "ODT-Mumbai", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "04-FEB-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "04-FEB-19", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5430, "PARENTREGIONID": 5349, "ISPARENT": 0, "NAME": "ODT-Dehradun", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "04-FEB-19", "LASTMODIFIEDBY": 5475, "LASTMODIFIEDON": "22-NOV-21", "ZIPCODE": None, "CATEGORYTYPE": 3},
        {"OWNERID": 721, "REGIONID": 5432, "PARENTREGIONID": 5362, "ISPARENT": 0, "NAME": "ODT-Raipur", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "04-FEB-19", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "04-FEB-19", "ZIPCODE": None, "CATEGORYTYPE": 3}
    ]

    # Two missing parent zones referenced as parents in the first 19:
    # 5349 (Northern Zone) and 5362 (Western Zone)
    missing_parents = [
        {"OWNERID": 721, "REGIONID": 5349, "PARENTREGIONID": 0, "ISPARENT": 1, "NAME": "Northern Zone", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "29-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 4},
        {"OWNERID": 721, "REGIONID": 5362, "PARENTREGIONID": 0, "ISPARENT": 1, "NAME": "Western Zone", "DESCRIPTION": None, "CREATEDBY": 1, "CREATEDON": "20-DEC-18", "LASTMODIFIEDBY": 1, "LASTMODIFIEDON": "29-JAN-19", "ZIPCODE": None, "CATEGORYTYPE": 4}
    ]

    # Combine them
    data = first_19 + missing_parents

    # Remaining 68 child rows to make 89 rows in total
    # Let's define child offices for the 4 parent zones
    # Parent Zones:
    # 5347 - Southern
    # 5348 - Eastern
    # 5349 - Northern
    # 5362 - Western

    # Let's generate a list of name details for the remaining 68 rows
    remaining_names = [
        # Southern Zone (5347)
        {"name": "BO Hyderabad", "parent": 5347},
        {"name": "CEPC Hyderabad", "parent": 5347},
        {"name": "ODT-Hyderabad", "parent": 5347},
        {"name": "BO Kochi", "parent": 5347},
        {"name": "ODT-Kochi", "parent": 5347},
        {"name": "BO Thiruvananthapuram", "parent": 5347},
        {"name": "CEPC Thiruvananthapuram", "parent": 5347},
        {"name": "ODT-Thiruvananthapuram", "parent": 5347},
        {"name": "BO Chennai", "parent": 5347},
        {"name": "CEPC Chennai", "parent": 5347},
        {"name": "ODT-Chennai", "parent": 5347},
        {"name": "BO Bengaluru", "parent": 5347},
        {"name": "ODT-Bengaluru", "parent": 5347},
        {"name": "NBFC Hyderabad", "parent": 5347},
        {"name": "NBFC Bengaluru", "parent": 5347},
        {"name": "CEPC Coimbatore", "parent": 5347},
        {"name": "BO Vijayawada", "parent": 5347},

        # Eastern Zone (5348)
        {"name": "BO Kolkata", "parent": 5348},
        {"name": "CEPC Kolkata", "parent": 5348},
        {"name": "ODT-Kolkata", "parent": 5348},
        {"name": "BO Patna", "parent": 5348},
        {"name": "CEPC Patna", "parent": 5348},
        {"name": "BO Bhubaneswar", "parent": 5348},
        {"name": "CEPC Bhubaneswar", "parent": 5348},
        {"name": "ODT-Bhubaneswar", "parent": 5348},
        {"name": "BO Ranchi", "parent": 5348},
        {"name": "CEPC Ranchi", "parent": 5348},
        {"name": "ODT-Ranchi", "parent": 5348},
        {"name": "BO Guwahati", "parent": 5348},
        {"name": "CEPC Guwahati", "parent": 5348},
        {"name": "ODT-Guwahati", "parent": 5348},
        {"name": "BO Imphal", "parent": 5348},
        {"name": "ODT-Imphal", "parent": 5348},

        # Northern Zone (5349)
        {"name": "BO New Delhi", "parent": 5349},
        {"name": "CEPC New Delhi", "parent": 5349},
        {"name": "ODT-New Delhi", "parent": 5349},
        {"name": "BO Jaipur", "parent": 5349},
        {"name": "CEPC Jaipur", "parent": 5349},
        {"name": "ODT-Jaipur", "parent": 5349},
        {"name": "BO Jammu", "parent": 5349},
        {"name": "ODT-Jammu", "parent": 5349},
        {"name": "CEPC Chandigarh", "parent": 5349},
        {"name": "BO Chandigarh", "parent": 5349},
        {"name": "ODT-Chandigarh", "parent": 5349},
        {"name": "BO Shimla", "parent": 5349},
        {"name": "CEPC Shimla", "parent": 5349},
        {"name": "ODT-Shimla", "parent": 5349},
        {"name": "BO Srinagar", "parent": 5349},
        {"name": "CEPC Srinagar", "parent": 5349},
        {"name": "ODT-Srinagar", "parent": 5349},

        # Western Zone (5362)
        {"name": "BO Mumbai", "parent": 5362},
        {"name": "CEPC Mumbai", "parent": 5362},
        {"name": "BO Ahmedabad", "parent": 5362},
        {"name": "ODT-Ahmedabad", "parent": 5362},
        {"name": "CEPC Bhopal", "parent": 5362},
        {"name": "ODT-Bhopal", "parent": 5362},
        {"name": "BO Surat", "parent": 5362},
        {"name": "CEPC Raipur", "parent": 5362},
        {"name": "BO Nagpur", "parent": 5362},
        {"name": "ODT-Nagpur", "parent": 5362},
        {"name": "BO Panaji", "parent": 5362},
        {"name": "ODT-Panaji", "parent": 5362},
        {"name": "BO Pune", "parent": 5362},
        {"name": "CEPC Pune", "parent": 5362},
        {"name": "ODT-Pune", "parent": 5362},
        {"name": "BO Indore", "parent": 5362},
        {"name": "CEPC Indore", "parent": 5362},
        {"name": "ODT-Indore", "parent": 5362}
    ]

    # Generate region IDs continuing from 5433 upwards
    current_region_id = 5433
    for office in remaining_names:
        # Avoid using IDs that are already used by the parents (5347, 5348, 5349, 5352, 5353, 5358, 5362, 5365, 5372, 5375, 5377, 5385, 5387, 5389, 5393, 5395, 5409, 5425, 5426, 5430, 5432)
        # 5433 onwards are all free.
        row = {
            "OWNERID": 721,
            "REGIONID": current_region_id,
            "PARENTREGIONID": office["parent"],
            "ISPARENT": 0,
            "NAME": office["name"],
            "DESCRIPTION": None,
            "CREATEDBY": 1,
            "CREATEDON": "30-JAN-19",
            "LASTMODIFIEDBY": 5475 if current_region_id % 3 == 0 else 1,
            "LASTMODIFIEDON": "22-JUN-20" if current_region_id % 3 == 0 else "30-JAN-19",
            "ZIPCODE": None,
            "CATEGORYTYPE": 3
        }
        data.append(row)
        current_region_id += 1

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Set missing column values to None / defaults
    df["CONTINENTID"] = None
    df["CONTINENTNAME"] = None
    df["ZONEID"] = None
    df["ZONENAME"] = None
    df["AREAID"] = None
    df["AREANAME"] = None
    df["CLUSTERID"] = None
    df["CLUSTERNAME"] = None
    df["BRANCHID"] = None
    df["BRANCHNAME"] = None
    df["LOCATIONID"] = None
    df["LOCATIONNAME"] = None
    
    # Non-null columns with default values in DB:
    df["PROCESSID"] = 0
    df["PROCESSVERSION"] = 0
    df["LAYOUTID"] = -1

    # Reorder columns to match original DB schema
    df = df[columns]

    # Write to Excel and CSV files in cms folder
    os.makedirs("project_data/cms", exist_ok=True)
    excel_path = "project_data/cms/regions.xlsx"
    csv_path = "project_data/cms/regions.csv"
    df.to_excel(excel_path, index=False)
    df.to_csv(csv_path, index=False)

    print(f"Regions dataset generation complete!")
    print(f"Generated {len(df)} rows.")
    print(f"Saved to: {excel_path} and {csv_path}")

if __name__ == "__main__":
    generate_regions()
