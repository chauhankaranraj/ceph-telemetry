#!/usr/bin/env python3
# vim: ts=4 sw=4 expandtab

import dbhelper
import psycopg2
import json
from pathlib import Path
from os import listdir
from os.path import isfile, join

"""
This script is to be run once when we move to the new db.
We go over the records in the report table and insert the latest reports 
into the other tables.
"""


DIR = '/home/yaarit/src/telemetry_db/raw'
# DIR = '/opt/telemetry/raw'

def run():
    conn = psycopg2.connect(host=dbhelper.HOST, dbname=dbhelper.DBNAME, user=dbhelper.USER, password=dbhelper.PASSWORD)
    cur = conn.cursor(name='my_cursor', withhold=True) # create a named server-side cursor
    # conn.setAutoCommit(false);

    print("aaaaaaaaaaaaaaa\n");
    cur.itersize = 10
    cur.execute("SELECT id, report FROM report ORDER BY cluster_id, timestamp")
    print("BBBBBBBBBBBBBB\n");

    i = 0;
    # check for errors
    for r in cur:
        i = i + 1
        if i % 100 == 0:
            print("at %s\n" % i)
        dbhelper.insert_into_all_tables(conn, r[0], json.loads(r[1]))

    # conn.commit() # Store the raw report even if the rest of the import fails
    cur.close()

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

