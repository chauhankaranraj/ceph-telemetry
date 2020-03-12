#!/usr/bin/env python3
# vim: ts=4 sw=4 expandtab

# TODO
# Add error handling
# Add logging 

import psycopg2
from psycopg2.extensions import AsIs
import os
import json
from os.path import isfile, join

#HOST = 'localhost'
HOST = '127.0.0.1'
DBNAME = 'teltest'
USER = 'testu'
PASSWORD = 'testu'

"""
USER = 'postgres'
PASSPATH = os.path.join(os.environ['HOME'], '.pgpass')
PASSWORD = open(PASSPATH, "r").read().strip().split(':')[-1]
"""


# FIXME replace 'j' with a short descriptive name (report_json is too long)
def import_raw_to_report_table(conn, report, j):
    cur = conn.cursor()

    # We don't use j.get() here because it's a fatal error if these fields do not exist
    cluster_id = j['report_id']  # The report_id in the json actually represents the cluster
    timestamp = j['report_timestamp']

    # Insert the report into 'report' table. We use it only for backup in case we need to regenerate the data
    cur.execute("""INSERT INTO report (cluster_id, timestamp, report) 
            VALUES (%s, %s, %s)
            RETURNING id""",
            (cluster_id, timestamp, report)
    )

    report_id_serial = cur.fetchone()[0]
    conn.commit() # Store the raw report even if the rest of the import fails

    return report_id_serial


def run_insert(cur, sql, d, extra_vals = ()):
    columns = d.keys()
    values = [d[column] for column in columns]

    cur.execute(sql, (AsIs(','.join(columns)), tuple(values)) + extra_vals)
    #print(cur.mogrify(sql, (AsIs(','.join(columns)), tuple(values))))

def run_insert_or_update(cur, i_sql, i_d, u_d, returning = None):
    i_columns = i_d.keys()
    i_values = [i_d[column] for column in i_columns]

    u_columns = u_d.keys()
    u_values = [u_d[column] for column in u_columns]

    sql = i_sql + ' ' + u_sql
    cur.execute(sql, 
            (AsIs(','.join(i_columns)), tuple(i_values)))


# FIXME replace 'j' with a short descriptive name (report_json is too long)
def insert_into_all_tables(conn, report_id_serial, j):
    cur = conn.cursor()

    cur.execute("DELETE FROM cluster WHERE cluster_id=%s", (j['report_id'],))

    cluster = {}
    cluster['report_id']            = report_id_serial
    cluster['cluster_id']           = j.get('report_id')
    # If a field does not exist in the json then it will be inserted as "null" to the database
    cluster['latest_report_timestamp'] = j.get('report_timestamp')
    cluster['created']			    = j.get('created')
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

    sql = 'INSERT INTO cluster (%s) VALUES %s RETURNING id'
    run_insert(cur, sql, cluster)
    cluster_id_serial = cur.fetchone()[0]

    for p in j.get('pools', []):
        pool = {}
        pool['cluster_id']              = cluster_id_serial
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

        sql = 'INSERT INTO pool (%s) VALUES %s'
        run_insert(cur, sql, pool)

    for entity, entity_val in j.get('metadata', {}).items():
        for attr, attr_val in entity_val.items():
            for value, total in attr_val.items():
                metadata = {}
                metadata['cluster_id']  = cluster_id_serial
                metadata['entity']      = entity
                metadata['attr']        = attr
                metadata['value']       = value
                metadata['total']       = total
                
                sql = 'INSERT INTO metadata (%s) VALUES %s'
                run_insert(cur, sql, metadata)


    for i in range(j.get('rbd', {}).get('num_pools', 0)):
        rbd_pool = {}
        rbd_pool['cluster_id']  = cluster_id_serial
        rbd_pool['pool_idx']    = i # This index is internal in the db
        rbd_pool['num_images']  = j['rbd']['num_images_by_pool'][i] # FIXME Will crash in case key is missing
        rbd_pool['mirroring']   = j['rbd']['mirroring_by_pool'][i]

        sql = 'INSERT INTO rbd_pool (%s) VALUES %s'
        run_insert(cur, sql, rbd_pool)


    # Commiting once, so everything is one transaction
    conn.commit()

