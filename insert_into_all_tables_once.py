#!/usr/bin/env python3
# vim: ts=4 sw=4 expandtab

import dbhelper
import psycopg2
import psycopg2.extras
import json
from pathlib import Path
from os import listdir
from os.path import isfile, join

"""
This script is to be run once when we move to the new db.
We go over the records in the report table and insert the latest reports 
into the other tables.
"""

# Data Source Name file
DSN = '/opt/telemetry/grafana.dsn'

"""
DIR = '/home/yaarit/src/telemetry_db/raw'
# DIR = '/opt/telemetry/raw'
"""

# FIXME replace 'j' with a short descriptive name (report_json is too long)
def insert_into_all_tables(conn, report_id_serial, j):
    cur = conn.cursor()

    #cur.execute("DELETE FROM grafana.cluster WHERE cluster_id=%s", (j['report_id'],))
    report_timestamp = j.get('report_timestamp')

    cluster = {}
    cluster['report_id']            = report_id_serial
    cluster['cluster_id']           = j.get('report_id')
    # If a field does not exist in the json then it will be inserted as "null" to the database
    #cluster['latest_report_timestamp'] = j.get('report_timestamp')
    cluster['ts']                   = report_timestamp
    cluster['created']			    = j.get('created')
    if cluster['created'] == '0.000000':
        print("Weird created value for cluster. Skipping\n")
        return
    cluster['channel_basic']		= 'basic' in j.get('channels', [])
    cluster['channel_crash']		= 'crash' in j.get('channels', [])
    cluster['channel_device']		= 'device' in j.get('channels', [])
    cluster['channel_ident']		= 'ident' in j.get('channels', [])

    cluster['total_bytes']	        = j.get('usage', {}).get('total_bytes')
    cluster['total_used_bytes']     = j.get('usage', {}).get('total_used_bytes')

    cluster['osd_count']		    = j.get('osd', {}).get('count')                    
    cluster['mon_count']		    = j.get('mon', {}).get('count')                    
    cluster['ipv4_addr_mons']		= j.get('mon', {}).get('ipv4_addr_mons')
    cluster['ipv6_addr_mons']		= j.get('mon', {}).get('ipv6_addr_mons')
    cluster['v1_addr_mons']		    = j.get('mon', {}).get('v1_addr_mons')
    cluster['v2_addr_mons']		    = j.get('mon', {}).get('v2_addr_mons')
                          
    cluster['rbd_num_pools']		= j.get('rbd', {}).get('num_pools')
                            
    cluster['fs_count']             = j.get('fs', {}).get('count')
    cluster['hosts_num']            = j.get('hosts', {}).get('num')
    cluster['pools_num']            = j.get('usage', {}).get('pools')
    # Compatibility with older telemetry modules
    cluster['pg_num']               = j.get('usage', {}).get('pg_num') or j.get('usage', {}).get('pg_num:') 

    #sql = 'INSERT INTO grafana.cluster (%s) VALUES %s RETURNING id'
    sql = 'INSERT INTO grafana.ts_cluster (%s) VALUES %s'
    dbhelper.run_insert(cur, sql, cluster)
    #cluster_id_serial = cur.fetchone()[0]

    for p in j.get('pools', []):
        pool = {}
        pool['ts']                      = report_timestamp
        pool['report_id']               = report_id_serial
        pool['pool_idx']                = p.get('pool') 
        pool['pgp_num']                 = p.get('pgp_num') 
        pool['pg_num']                  = p.get('pg_num')
        pool['size']                    = p.get('size')
        pool['min_size']                = p.get('min_size')
        pool['cache_mode']              = p.get('cache_mode')
        pool['target_max_objects']      = p.get('target_max_objects')
        pool['target_max_bytes']        = p.get('target_max_bytes')
        pool['pg_autoscale_mode']       = p.get('pg_autoscale_mode')
        pool['type']                    = p.get('type')
        pool['ec_k']                    = p.get('erasure_code_profile', {}).get('k')
        pool['ec_m']                    = p.get('erasure_code_profile', {}).get('m')
        pool['ec_crush_failure_domain'] = p.get('erasure_code_profile', {}).get('crush_failure_domain')
        pool['ec_plugin']               = p.get('erasure_code_profile', {}).get('plugin')
        pool['ec_technique']            = p.get('erasure_code_profile', {}).get('technique')

        sql = 'INSERT INTO grafana.pool (%s) VALUES %s'
        dbhelper.run_insert(cur, sql, pool)

    for entity, entity_val in j.get('metadata', {}).items():
        for attr, attr_val in entity_val.items():
            for value, total in attr_val.items():
                metadata = {}
                metadata['ts']          = report_timestamp
                metadata['report_id']   = report_id_serial
                metadata['entity']      = entity
                metadata['attr']        = attr
                metadata['value']       = value
                metadata['total']       = total
                
                sql = 'INSERT INTO grafana.metadata (%s) VALUES %s'
                dbhelper.run_insert(cur, sql, metadata)
                # Normalize 'ceph_version' - extract the numeric version part
                if attr == 'ceph_version':
                    metadata['attr'] = 'ceph_version_norm'
                    metadata['value'] = re.match('ceph version v*([0-9.]+|Dev).*', value).group(1)
                    dbhelper.run_insert(cur, sql, metadata)

    for i in range(j.get('rbd', {}).get('num_pools', 0)):
        rbd_pool = {}
        rbd_pool['ts']          = report_timestamp
        rbd_pool['report_id']   = report_id_serial
        rbd_pool['pool_idx']    = i # This index is internal in the db
        rbd_pool['num_images']  = j['rbd']['num_images_by_pool'][i] # FIXME Will crash in case key is missing
        rbd_pool['mirroring']   = j['rbd']['mirroring_by_pool'][i]

        sql = 'INSERT INTO grafana.rbd_pool (%s) VALUES %s'
        dbhelper.run_insert(cur, sql, rbd_pool)


    # Commiting once, so everything is one transaction
    conn.commit()

def run():
    with open(DSN, 'r') as f:
        dsn_str = f.read().strip()

    conn = psycopg2.connect(dsn_str)
    #cur = conn.cursor(name='my_cursor', withhold=True) # create a named server-side cursor
    # Create a named server-side cursor
    dict_cur = conn.cursor(name='server_side_cursor', withhold=True, cursor_factory=psycopg2.extras.DictCursor)
    # conn.setAutoCommit(false);

    dict_cur.itersize = 10
    dict_cur.execute("SELECT id, report FROM public.report ORDER BY cluster_id, report_stamp")

    '''
    dict_cur.execute("""SELECT id, report_stamp, report, id 
                    FROM public.report 
                    WHERE id > (SELECT var_value 
                                FROM grafana.device_inserter_state 
                                WHERE var_name = 'last_inserted_report_id')
                    ORDER BY timestamp
                    """)
    '''


    i = 0;
    # check for errors
    for r in dict_cur:
        i += 1
        if i % 100 == 0:
            print("at %s\n" % i)
        insert_into_all_tables(conn, r['id'], json.loads(r['report']))

    # conn.commit() # Store the raw report even if the rest of the import fails
    dict_cur.close()

    """
    files = [f for f in listdir(DIR) if isfile(join(DIR, f))]
    for fname in files:
        report = Path(DIR + '/' + fname).read_text()
        j = json.loads(report)
        # We use json.dumps(j) since the report is pretty printed
        # and we want to save space in the db.
        dbhelper.import_raw_to_report_table(conn, json.dumps(j), j)
    """

run()

