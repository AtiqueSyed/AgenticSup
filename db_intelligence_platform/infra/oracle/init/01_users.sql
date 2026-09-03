-- Two PDB-local users, one per "database" in the demo: CMS and DAKSH.
--
-- Why no cross-schema grants: the onboarding schema introspector
-- (src/agents/onboarding/schema_extractor.py) lists every visible schema via
-- ALL_USERS and then calls get_table_names(schema=X) for each one it finds. If CMS
-- could see DAKSH's tables (or vice versa), onboarding either user would ingest both
-- schemas and the two "separate databases" would collapse into one. Session +
-- table-create + quota on USERS is the whole grant set on purpose -- no DBA, no
-- SELECT ANY TABLE, no grants between the two users.
--
-- Runs once, on first database creation. gvenzl's entrypoint actually executes
-- container-entrypoint-initdb.d scripts against CDB$ROOT (con_id 1), not the PDB --
-- despite the mount point's docs implying otherwise. CREATE USER there makes a common
-- user that also shows up in FREEPDB1, but a plain GRANT with no CONTAINER clause only
-- applies to the root: the PDB copy of the user ends up with zero privileges and every
-- connection to FREEPDB1 as CMS/DAKSH fails with ORA-01045. Switching into the PDB
-- first makes the CREATE USER/GRANT/ALTER USER statements below apply directly to
-- FREEPDB1, where the app actually connects.
--
-- No C## prefix needed: even though we're one ALTER SESSION away from CDB$ROOT, these
-- users are created inside the PDB, not as common users.

ALTER SESSION SET CONTAINER = FREEPDB1;

CREATE USER CMS IDENTIFIED BY cms;
GRANT CREATE SESSION TO CMS;
GRANT CREATE TABLE TO CMS;
ALTER USER CMS QUOTA UNLIMITED ON USERS;

CREATE USER DAKSH IDENTIFIED BY daksh;
GRANT CREATE SESSION TO DAKSH;
GRANT CREATE TABLE TO DAKSH;
ALTER USER DAKSH QUOTA UNLIMITED ON USERS;
