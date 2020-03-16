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


