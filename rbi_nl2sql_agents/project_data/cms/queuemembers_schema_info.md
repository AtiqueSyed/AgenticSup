# CRMNEXT.queuemembers Schema and Sample Dataset

## Table DDL
```sql
CREATE TABLE CRMNEXT.queuemembers (
    OWNERID NUMBER(10,0) NOT NULL,
    QUEUEID NUMBER(10,0) NOT NULL,
    QUEUETYPE NUMBER(10,0),
    MEMBERID NUMBER(10,0) NOT NULL,
    LASTMODIFIEDBYTYPE NUMBER(10,0) NOT NULL,
    ADDEDBY NUMBER(10,0) NOT NULL,
    SHOWQUEUEMEMBERS NUMBER(10,0),
    IPADDRESS NVARCHAR2(50 CHAR),
    CONSTRAINT PK_QUEUEMEMBERS PRIMARY KEY (QUEUEID, MEMBERID)
);
```

## Description of Key Columns
- **OWNERID**: Always `721`.
- **QUEUEID**: The unique identifier of the queue, referencing the `QUEUE` table.
- **QUEUETYPE**: The queue type identifier (mostly `2`, matching the category of the queue).
- **MEMBERID**: The unique identifier of the queue member (user).
- **LASTMODIFIEDBYTYPE**: Modifier type code (commonly `-1` or `0`).
- **ADDEDBY**: The user identifier of the operator who added the member to the queue (e.g., `1`, `5477`, `11728`, etc.).
- **SHOWQUEUEMEMBERS**: Boolean preference flag (defaults to `0`).
- **IPADDRESS**: Connection IP address.

## Sample Dataset of Important Columns
Below is a sample of the first 14 rows matching the schema configuration:

| OWNERID | QUEUEID | QUEUETYPE | MEMBERID | LASTMODIFIEDBYTYPE | ADDEDBY | SHOWQUEUEMEMBERS | IPADDRESS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 721 | 5349 | 2 | 5918 | -1 | 11728 | 0 | (null) |
| 721 | 5379 | 2 | 12674 | -1 | 11551 | 0 | (null) |
| 721 | 5333 | 2 | 14123 | -1 | 13023 | 0 | (null) |
| 721 | 5359 | 2 | 14100 | -1 | 5650 | 0 | (null) |
| 721 | 5349 | 2 | 11099 | -1 | 5475 | 0 | (null) |
| 721 | 5383 | 2 | 5635 | -1 | 11479 | 0 | (null) |
| 721 | 5369 | 2 | 6011 | -1 | 5635 | 0 | (null) |
| 721 | 5383 | 2 | 5628 | -1 | 11479 | 0 | (null) |
| 721 | 5369 | 2 | 7127 | -1 | 5477 | 0 | (null) |
| 721 | 5347 | 2 | 15750 | -1 | 5475 | 0 | (null) |
| 721 | 5359 | 2 | 5814 | -1 | 5826 | 0 | (null) |
| 721 | 5350 | 2 | 5400 | 0 | 1 | 0 | (null) |
| 721 | 5352 | 2 | 5393 | 0 | 1 | 0 | (null) |
| 721 | 5353 | 2 | 5393 | 0 | 1 | 0 | (null) |
