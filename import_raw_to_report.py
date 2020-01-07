#!/usr/bin/env python3
# vim: ts=4 sw=4 expandtab

import dbhelper
import psycopg2
import json
from pathlib import Path
from os import listdir
from os.path import isfile, join

DIR = '/home/yaarit/src/telemetry_db/raw'
# DIR = '/opt/telemetry/raw'

def run():
    conn = psycopg2.connect(host=dbhelper.HOST, dbname=dbhelper.DBNAME, user=dbhelper.USER, password=dbhelper.PASSWORD)
    cur = conn.cursor()
    # conn.setAutoCommit(false);
    files = [f for f in listdir(DIR) if isfile(join(DIR, f))]
    for fname in files:
        report = Path(DIR + '/' + fname).read_text()
        j = json.loads(report)
        # We use json.dumps(j) since the report is pretty printed
        # and we want to save space in the db.
        dbhelper.import_raw_to_report_table(conn, json.dumps(j), j)


run()


