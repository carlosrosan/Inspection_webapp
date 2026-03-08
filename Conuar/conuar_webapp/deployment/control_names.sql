-- Table: control_names
-- Lookup table for ID_Control (ID in Excel) -> Control Name (Medicion in Excel).
--
-- 1) Run this script to create the table (from project root or DB client):
--    sqlite3 db.sqlite3 < "1. Inspection webapp/control_names.sql"
--    or execute the CREATE TABLE below in your DB client.
--
-- 2) Load data from "Numero de SE y barra.xlsx":
--    cd "1. Inspection webapp"
--    python load_control_names_from_excel.py --output control_names_data.sql
--    Then run the generated control_names_data.sql, OR:
--    python load_control_names_from_excel.py --django   (inserts via Django, from project root)
--

-- DROP TABLE IF EXISTS control_names;   -- uncomment to recreate

CREATE TABLE IF NOT EXISTS control_names (
    id_control VARCHAR(50) NOT NULL PRIMARY KEY,
    control_name VARCHAR(255) NOT NULL
);
