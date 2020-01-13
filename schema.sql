/*
Getting all reports that were not processed yet:
  max = "select max(report_id) from cluster";
  new_reports = "select * from reports where id > $max";
*/
\echo Creating table report
CREATE TABLE report (
	id			SERIAL PRIMARY KEY,
	cluster_id		VARCHAR(50),
	timestamp		TIMESTAMP,
	report			TEXT,
	UNIQUE (cluster_id, timestamp)
);

\echo Creating table cluster
CREATE TABLE cluster (
	id			SERIAL PRIMARY KEY,
	report_id		INTEGER REFERENCES report(id),
	cluster_id 		VARCHAR(50)	UNIQUE,
	created			TIMESTAMP, /* cluster creation date */
	latest_report_timestamp	TIMESTAMP,
	channel_basic		BOOLEAN,
	channel_crash		BOOLEAN,
	channel_device		BOOLEAN,
	channel_ident		BOOLEAN,
	
	total_bytes		BIGINT,
	total_used_bytes	BIGINT,
	osd_count		INTEGER,

	mon_count		INTEGER,
	ipv4_addr_mons		INTEGER,
	ipv6_addr_mons		INTEGER,
	v1_addr_mons		INTEGER,
	v2_addr_mons		INTEGER,

	rbd_num_pools		INTEGER, /* do we want it here? */	

	fs_count		INTEGER,
	hosts_num		INTEGER,
	pools_num		INTEGER,
	pg_num			INTEGER
);


/*
  "metadata": {
    "osd": {
      "cpu": {
        "Intel(R) Xeon(R) CPU E5-2620 v4 @ 2.10GHz": 90
      },
    }
  }
translates to:
    INSERT INTO metadata (cluster_id, entity, attr, value, total)
      VALUES ($cluster_id, "osd", "cpu", "Intel(R) Xeon(R) CPU E5-2620 v4 @ 2.10GHz", 90);

example query - number of different ceph versions per cluster:
SELECT COUNT(DISTINCT(value)) FROM metadata WHERE cluster_id=$cluster_id AND attr="ceph_version";
*/

\echo Creating table metadata
CREATE TABLE metadata (
	cluster_id		INTEGER REFERENCES cluster(id) ON DELETE CASCADE,
	entity			VARCHAR(16),
	attr			VARCHAR(32),
	value			VARCHAR(128),
	total			INTEGER
);

\echo Creating table rbd_pool
CREATE TABLE rbd_pool (
	cluster_id		INTEGER REFERENCES cluster(id) ON DELETE CASCADE,
	pool_idx		INTEGER, /* needs to derive this from the element position in the array */
	num_images		INTEGER,
	mirroring		BOOLEAN
);

\echo Creating table pool 
CREATE TABLE pool (
	cluster_id		INTEGER REFERENCES cluster(id) ON DELETE CASCADE,
	pool_idx		INTEGER,
	pgp_num			INTEGER,
	pg_num			INTEGER,
	size			INTEGER,
	min_size		INTEGER,
	cache_mode		VARCHAR(32),
	target_max_objects	INTEGER,
	target_max_bytes	INTEGER,
	pg_autoscale_mode	VARCHAR(32),
	type			VARCHAR(32),

	/* erasure_code_profile */
	ec_k			SMALLINT,
	ec_m			SMALLINT,
	ec_crush_failure_domain	VARCHAR(32),
	ec_plugin		VARCHAR(32),
	ec_technique		VARCHAR(32)
);

/* Keep the crash table the same as in the old database for now */
\echo Creating crash table
CREATE TABLE crash (
	crash_id		VARCHAR(128) PRIMARY KEY,
	cluster_id		VARCHAR(50),
	raw_report		TEXT,
	timestamp		TIMESTAMP,
	entity_name		CHAR(64),
	version			VARCHAR(64),
	stack_sig		VARCHAR(64),
	stack			TEXT
);
