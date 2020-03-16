/*
Getting all reports that were not processed yet:
  max = "select max(report_id) from cluster";
  new_reports = "select * from reports where id > $max";
*/

/*
CREATE TABLE report (
	id			SERIAL PRIMARY KEY,
	cluster_id		VARCHAR(50),
	timestamp		TIMESTAMP,
	report			TEXT,
	UNIQUE (cluster_id, timestamp)
);
*/

CREATE TABLE grafana.ts_cluster (
	-- id			SERIAL PRIMARY KEY,
	report_id		INTEGER REFERENCES public.report(id) PRIMARY KEY,
	ts			TIMESTAMP,
	cluster_id 		VARCHAR(50),
	created			TIMESTAMP, /* cluster creation date */
	-- latest_report_timestamp	TIMESTAMP,
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
    INSERT INTO metadata (report_id, entity, attr, value, total)
      VALUES ($report_id, "osd", "cpu", "Intel(R) Xeon(R) CPU E5-2620 v4 @ 2.10GHz", 90);

example query - number of different ceph versions per cluster:
SELECT COUNT(DISTINCT(value)) FROM metadata WHERE report_id=$report_id AND attr="ceph_version";
*/

CREATE TABLE grafana.metadata (
	report_id		INTEGER REFERENCES public.report(id) ON DELETE CASCADE,
	ts			TIMESTAMP,
	entity			VARCHAR(16),
	attr			VARCHAR(32),
	value			VARCHAR(128),
	total			INTEGER
);

CREATE TABLE grafana.rbd_pool (
	report_id		INTEGER REFERENCES public.report(id) ON DELETE CASCADE,
	ts			TIMESTAMP,
	pool_idx		INTEGER, /* needs to derive this from the element position in the array */
	num_images		INTEGER,
	mirroring		BOOLEAN
);

CREATE TABLE grafana.pool (
	report_id		INTEGER REFERENCES public.report(id) ON DELETE CASCADE,
	ts			TIMESTAMP,
	pool_idx		INTEGER,
	pgp_num			INTEGER,
	pg_num			INTEGER,
	size			BIGINT,
	min_size		BIGINT,
	cache_mode		VARCHAR(32),
	target_max_objects	BIGINT,
	target_max_bytes	BIGINT,
	pg_autoscale_mode	VARCHAR(32),
	type			VARCHAR(32),

	/* erasure_code_profile */
	ec_k			SMALLINT,
	ec_m			SMALLINT,
	ec_crush_failure_domain	VARCHAR(32),
	ec_plugin		VARCHAR(32),
	ec_technique		VARCHAR(32)
);
