# CRMNEXT.regions Schema and Sample Dataset

## Table DDL
```sql
CREATE TABLE CRMNEXT.regions (
    OWNERID NUMBER(10,0) NOT NULL,
    REGIONID NUMBER(10,0) NOT NULL,
    PARENTREGIONID NUMBER(10,0),
    ISPARENT NUMBER(1,0),
    NAME NVARCHAR2(256) NOT NULL,
    DESCRIPTION NVARCHAR2(2048),
    CREATEDBY NUMBER(10,0),
    CREATEDON DATE,
    LASTMODIFIEDBY NUMBER(10,0),
    LASTMODIFIEDON DATE,
    ZIPCODE NVARCHAR2(64),
    CATEGORYTYPE NUMBER(10,0) NOT NULL,
    CONTINENTID NUMBER(10,0),
    CONTINENTNAME NVARCHAR2(256),
    ZONEID NUMBER(10,0),
    ZONENAME NVARCHAR2(256),
    AREAID NUMBER(10,0),
    AREANAME NVARCHAR2(256),
    CLUSTERID NUMBER(10,0),
    CLUSTERNAME NVARCHAR2(256),
    BRANCHID NUMBER(10,0),
    BRANCHNAME NVARCHAR2(256),
    LOCATIONID NUMBER(10,0),
    LOCATIONNAME NVARCHAR2(256),
    PROCESSID NUMBER(10,0) NOT NULL,
    PROCESSVERSION NUMBER(10,0) NOT NULL,
    LAYOUTID NUMBER(10,0) NOT NULL,
    CONSTRAINT PK_REGIONS PRIMARY KEY (REGIONID)
);
```

## Description of Key Columns
- **OWNERID**: Always `721`.
- **REGIONID**: The unique identifier of the region/office, sequenced starting at `5347`.
- **PARENTREGIONID**: The parent zone ID (e.g. `5347` for Southern, `5348` for Eastern, `5349` for Northern, `5362` for Western) or `0` for parent zones.
- **ISPARENT**: Binary flag (`1` for parent zones, `0` for child offices).
- **NAME**: The name of the region or office (e.g., "Southern Zone", "BO Raipur", "CEPC-Bhopal").
- **CATEGORYTYPE**: `4` for parent zones, `3` for child offices (defaults to `1` in schema).

## Sample Dataset of Important Columns
Below is a sample of the first 19 rows matching the schema configuration:

| OWNERID | REGIONID | PARENTREGIONID | ISPARENT | NAME | CREATEDON | LASTMODIFIEDON | CATEGORYTYPE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 721 | 5347 | 0 | 1 | Southern Zone | 20-DEC-18 | 29-JAN-19 | 4 |
| 721 | 5348 | 0 | 1 | Eastern Zone | 20-DEC-18 | 29-JAN-19 | 4 |
| 721 | 5353 | 5362 | 0 | BO Raipur | 20-DEC-18 | 22-JUN-20 | 3 |
| 721 | 5352 | 5362 | 0 | BO Bhopal | 20-DEC-18 | 22-JUN-20 | 3 |
| 721 | 5358 | 5347 | 0 | NBFC Chennai | 20-DEC-18 | 22-JAN-19 | 3 |
| 721 | 5365 | 5362 | 0 | CEPD Mumbai | 03-JAN-19 | 22-JAN-19 | 3 |
| 721 | 5372 | 5362 | 0 | CEPC Ahmedabad | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5375 | 5347 | 0 | CEPC Bengaluru | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5377 | 5348 | 0 | CEPC-Bhopal | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5385 | 5348 | 0 | CEPC-Imphal | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5387 | 5349 | 0 | CEPC-Jammu | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5389 | 5347 | 0 | CEPC-Kochi | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5409 | 5349 | 0 | BO Dehradun | 31-JAN-19 | 31-JAN-19 | 3 |
| 721 | 5393 | 5362 | 0 | CEPC-Nagpur | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5395 | 5362 | 0 | CEPC-Panaji | 30-JAN-19 | 30-JAN-19 | 3 |
| 721 | 5425 | 5348 | 0 | ODT-Patna | 04-FEB-19 | 22-JUN-20 | 3 |
| 721 | 5426 | 5362 | 0 | ODT-Mumbai | 04-FEB-19 | 04-FEB-19 | 3 |
| 721 | 5430 | 5349 | 0 | ODT-Dehradun | 04-FEB-19 | 22-NOV-21 | 3 |
| 721 | 5432 | 5362 | 0 | ODT-Raipur | 04-FEB-19 | 04-FEB-19 | 3 |
