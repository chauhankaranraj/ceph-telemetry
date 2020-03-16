--\echo Creating schema grafana
DROP SCHEMA IF EXISTS grafana CASCADE;
CREATE SCHEMA IF NOT EXISTS grafana;

--\echo Creating type interface_type
DROP TYPE IF EXISTS grafana.interface_type;
CREATE TYPE grafana.interface_type AS ENUM ('ata', 'sata', 'sas', 'scsi', 'nvme');

--\echo Creating type device_type
-- maybe need to change ssd to flash
DROP TYPE IF EXISTS grafana.device_type;
CREATE TYPE grafana.device_type AS ENUM ('hdd', 'ssd');

--\echo Creating table device
CREATE TABLE grafana.device (
        id                      SERIAL PRIMARY KEY,
        dev_id                  VARCHAR(128) UNIQUE,
        vendor                  VARCHAR(128),
        model                   VARCHAR(128),
        --interface             VARCHAR(16),
        host_id                 VARCHAR(128),
        type                    grafana.device_type,
	interface               grafana.interface_type,
	first_report            TIMESTAMP,
        last_report             TIMESTAMP,
        report_count            INTEGER,
        error                   TEXT
);

--\echo Creating table device_smart_sata
CREATE TABLE grafana.device_smart_sata (
        device_id               INTEGER REFERENCES grafana.device(id) ON DELETE CASCADE,
        created                 TIMESTAMP,
        attr_id                 INTEGER,
	attr_name		VARCHAR(128),
        attr_val                BIGINT,
	attr_val_str		VARCHAR(128),
	attr_worst		BIGINT
);

--\echo Creating table device_smart_nvme
CREATE TABLE grafana.device_smart_nvme (
        device_id               INTEGER REFERENCES grafana.device(id) ON DELETE CASCADE,
        created                 TIMESTAMP,
	attr_name		VARCHAR(128),
        attr_val                BIGINT,
        attr_val_err            TEXT --In case attr_val could not be retrieved 
);

-- Device's vendor specific extended SMART 'log page contents'
--\echo Creating table device_smart_nvme_vs
CREATE TABLE grafana.device_smart_nvme_vs (
        device_id               INTEGER REFERENCES grafana.device(id) ON DELETE CASCADE,
        created                 TIMESTAMP,
	attr_name		VARCHAR(128),
        attr_val                BIGINT,
        attr_val_err            TEXT --In case attr_val could not be retrieved 
);

--\echo Creating table device_inserter_state
CREATE TABLE grafana.device_inserter_state (
 	var_name		VARCHAR(32) PRIMARY KEY,
        var_value	        INTEGER
);

GRANT usage ON SCHEMA grafana TO grafana;
GRANT ALL ON ALL TABLES IN SCHEMA grafana TO grafana;
GRANT ALL ON ALL SEQUENCES IN SCHEMA grafana TO grafana;

INSERT INTO grafana.device_inserter_state
	(var_name, var_value)
VALUES
	('last_inserted_id', -1);
