-- Table: control_names
-- Lookup from Excel "Info de fotos.xlsx". Multiple rows per control_id (one per photo/variant).
-- Columns: control_id, control_name, valor_esperado, tolerancia, separador, barra, pos_z_carro, pos_x_plato
--
-- 1) Run this script to create the table (from project root or DB client):
--    sqlite3 db.sqlite3 < "1. Inspection webapp/control_names.sql"
--
-- 2) Load data from "Info de fotos.xlsx":
--    cd "1. Inspection webapp"
--    python load_control_names_from_excel.py --output control_names_data.sql
--    Then run the generated control_names_data.sql, OR:
--    python load_control_names_from_excel.py --django
--

-- DROP TABLE IF EXISTS control_names;   -- uncomment to recreate

CREATE TABLE IF NOT EXISTS control_names (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    control_id VARCHAR(50) NOT NULL,
    control_name VARCHAR(255) NOT NULL,
    valor_esperado VARCHAR(255) NULL,
    tolerancia VARCHAR(255) NULL,
    separador VARCHAR(255) NULL,
    barra VARCHAR(255) NULL,
    pos_z_carro VARCHAR(255) NULL,
    pos_x_plato VARCHAR(255) NULL
);

-- Index for lookups by control_id (multiple rows per control_id)
CREATE INDEX IF NOT EXISTS idx_control_names_control_id ON control_names(control_id);
