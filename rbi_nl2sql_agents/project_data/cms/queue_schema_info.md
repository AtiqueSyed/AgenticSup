# CRMNEXT.QUEUE Schema and Sample Dataset

## Table DDL
```sql
CREATE TABLE CRMNEXT.QUEUE (
    OWNERID NUMBER(10,0) NOT NULL,
    QUEUEID NUMBER(10,0) NOT NULL,
    QUEUETYPE NUMBER(10,0) NOT NULL,
    NAME NVARCHAR2(256) NOT NULL,
    DESCRIPTION NVARCHAR2(2048),
    CREATEDON DATE NOT NULL,
    CREATEDBY NUMBER(10,0) NOT NULL,
    LASTMODIFIEDON DATE NOT NULL,
    LASTMODIFIEDBY NUMBER(10,0) NOT NULL,
    DEFAULTOWNERID NUMBER(10,0) NOT NULL,
    STARTTIME DATE,
    ENDTIME DATE,
    ISACTIVE NUMBER(1,0) NOT NULL,
    EXECUTIONORDER NUMBER(10,0) NOT NULL,
    BUSINESSUNITID NUMBER(10,0) NOT NULL,
    ASSIGNMENTONLYLOGGEDINUSER NUMBER(1,0) NOT NULL,
    UNIQUEID CHAR(36 CHAR) NOT NULL,
    LASTMODIFIEDBYTYPE NUMBER(10,0) NOT NULL,
    STARTMIN NUMBER,
    ENDMIN NUMBER,
    QUEUECRITERIA NCLOB,
    IPADDRESS NVARCHAR2(50 CHAR),
    CONSTRAINT PK_QUEUE PRIMARY KEY (QUEUEID)
);
```

## Description of Key Columns
- **OWNERID**: Always `721`.
- **QUEUEID**: The unique identifier of the queue, sequenced starting at `5333` up to `5387`.
- **QUEUETYPE**: Category identifier (mostly `2`, with `8` for Regional Admins and `3` for Approver).
- **NAME**: The name of the queue (e.g. "NBFC Admin queue", "CEPD DO Queue", "RBIO Ombudsman Queue").
- **DEFAULTOWNERID**: Primary user group/owner identifier (defaults to `1`, but commonly `77` or `75`).
- **ISACTIVE**: Binary flag (`1` for active queues, `0` for inactive).
- **EXECUTIONORDER**: Integer ordering parameter.
- **UNIQUEID**: Unique identifier string (formatted as UUID).
- **IPADDRESS**: Connection IP address.

## Sample Dataset of Important Columns
Below is a sample of the first 22 rows matching the schema configuration:

| OWNERID | QUEUEID | QUEUETYPE | NAME | CREATEDON | LASTMODIFIEDON | DEFAULTOWNERID | ISACTIVE | EXECUTIONORDER | IPADDRESS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 721 | 5340 | 2 | NBFC Admin queue | 17-DEC-18 | 26-MAR-19 | 77 | 1 | 7 | 10.21.1.6 |
| 721 | 5350 | 2 | Sent to Contact Person | 02-JAN-19 | 04-JAN-19 | 77 | 0 | 15 | 10.21.1.6 |
| 721 | 5358 | 2 | Centralized Officers | 04-JAN-19 | 04-JAN-19 | 1 | 1 | 23 | 10.21.1.6 |
| 721 | 5359 | 2 | Draft Complaint Dealing Official queue | 04-JAN-19 | 04-JAN-19 | 1 | 1 | 24 | 114.143.24.24 |
| 721 | 5333 | 2 | BO Dealing Official queue | 23-NOV-18 | 24-MAY-19 | 77 | 1 | 0 | 114.143.24.24 |
| 721 | 5336 | 2 | Banking Ombudsman queue | 23-NOV-18 | 26-MAR-19 | 77 | 1 | 3 | ::1 |
| 721 | 5339 | 2 | CEPC Admin | 14-DEC-18 | 26-MAR-19 | 77 | 1 | 6 | 10.21.1.6 |
| 721 | 5341 | 2 | NBFC Reviewer Queue | 17-DEC-18 | 26-MAR-19 | 77 | 1 | 8 | 10.21.1.6 |
| 721 | 5343 | 2 | NBFC Secretary to NBFC Queue | 17-DEC-18 | 01-APR-19 | 77 | 0 | 10 | 10.21.1.6 |
| 721 | 5344 | 2 | NBFC Queue | 17-DEC-18 | 26-MAR-19 | 77 | 1 | 11 | 10.21.1.6 |
| 721 | 5349 | 2 | Sent to Operational In charge | 02-JAN-19 | 26-MAR-19 | 77 | 1 | 14 | 10.21.1.6 |
| 721 | 5351 | 2 | Sent to CEPC In charge | 02-JAN-19 | 26-MAR-19 | 77 | 0 | 16 | 10.21.1.6 |
| 721 | 5353 | 2 | Sent back to CEPC Operational In charge /Sent to Closing Authority | 02-JAN-19 | 26-MAR-19 | 77 | 0 | 18 | 10.21.1.6 |
| 721 | 5363 | 2 | CEPC_DOUser | 23-JAN-19 | 24-MAY-19 | 77 | 1 | 28 | 10.21.1.6 |
| 721 | 5338 | 2 | Inward Officials BO Queue | 07-DEC-18 | 23-OCT-19 | 77 | 1 | 5 | 10.21.1.6 |
| 721 | 5347 | 2 | AA DO | 31-DEC-18 | 31-DEC-18 | 1 | 1 | 13 | 172.16.24.5 |
| 721 | 5354 | 2 | Sent back to CEPC In charge/Mark For Closure | 02-JAN-19 | 26-MAR-19 | 77 | 0 | 19 | 114.143.24.24 |
| 721 | 5360 | 2 | Common Role | 10-JAN-19 | 26-MAR-19 | 77 | 1 | 25 | 10.21.1.6 |
| 721 | 5362 | 2 | CEPD Admin | 11-JAN-19 | 11-JAN-19 | 1 | 1 | 27 | 10.21.1.6 |
| 721 | 5364 | 2 | CEPC-InchargeUser | 23-JAN-19 | 26-MAR-19 | 77 | 1 | 29 | 114.143.24.24 |
| 721 | 5334 | 2 | Inward Official NBFC Queue | 23-NOV-18 | 17-OCT-19 | 75 | 1 | 1 | 10.21.1.6 |
| 721 | 5337 | 2 | BO Admin queue | 05-DEC-18 | 25-FEB-20 | 77 | 1 | 4 | 172.16.24.5 |
