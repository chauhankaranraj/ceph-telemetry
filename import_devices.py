#!/usr/bin/env python3
# vim: ts=4 sw=4 expandtab

import dbhelper
import psycopg2
import psycopg2.extras
import json
import sys
import time
from pathlib import Path
from os import listdir
from os.path import isfile, join

# Data Source Name file
DSN = '/opt/telemetry/grafana.dsn'

# TODO:
#    1. pay attention to differences between 
#       report timestamp
#       and smart scrape time
#    2. verify timestamp is ok due to the changes in nautilus and octapus 
#    3. note: currentaly if we iterate over reports in device_report
#       which are already in device table - the counter will be increamented 
#       and the last_report will be updated as well.
#    4. add postgres logs?
#    5. add SMART firmaware version to 'device' table
#    6. nvme's smart output (at least for intel ones) has capacity, size and untilization sections.
#       On intel they all equal. check if utilization is different than capacity in any other nvme model
#    7. Add device size to "device"
#    8. Email errors 

#  Next step:
#   - Parse the nvme_smart_health_information_log section. if the "val" is a dict, save the 'n' part of it. Alert if
#       the 'n' and 's' parts differ.
#   - Recursively parse the nvme_smart_health_information_add_log/device_stats section.
#   - check if nvme_smart_health_information_add_log is added via blkdev.cc

#   - ADD THE DSN FILE TO THE COMMIT
#   - Add serial 
#   - Run this in the server:
#     alter table device_report add column id serial;
#     create unique index on device_report (id);
#   - Add this to tables.txt:
#   - https://stackoverflow.com/questions/53370072/add-auto-increment-column-to-existing-table-ordered-by-date
"""
CREATE TABLE public.device_report (
	device_id varchar(128) NULL,
	report_stamp timestamp NULL,
	report text NULL,
	id serial NOT NULL
);
CREATE UNIQUE INDEX public.device_report_id_idx ON public.device_report (id);

or:
    ALTER TABLE public.device_report ADD COLUMN "id" SERIAL NOT NULL;
    CREATE UNIQUE INDEX ON public.device_report (id);
"""


def parse_nvme_vendor(prefix, data, result):
    if not isinstance(data, dict):
        result[prefix] = data
    else:
        for k in data.keys():
            parse_nvme_vendor(prefix + '_' + k, data[k], result)


def import_report(conn, r):
    cur = conn.cursor()
    dev_id = r['device_id']
    ts = r['report_stamp']
    rep = json.loads(r['report'])
    last_inserted_id = r['id']

    device = {}
    device['dev_id']    = dev_id
    device['vendor']    = dev_id[: dev_id.find('_')]
    # verify dev_id.count('_') > 1 ?
    device['model']     = dev_id[dev_id.find('_') + 1 : dev_id.rfind('_')]
    device['host_id']   = rep.get('host_id', None)
    device['first_report']  = device['last_report'] = ts
    device['report_count']  = 1

    device['error'] = rep.get('error')
    interface = rep.get('device', {}).get('protocol')
    device['interface'] = interface.lower() if interface else None
    # TODO check type: spinning or flash
    #device['type'] =

    sql = """INSERT INTO grafana.device (%s) VALUES %s
            ON CONFLICT (dev_id) DO UPDATE
            SET report_count = grafana.device.report_count + 1
            , interface = %s
            , error = %s
            , last_report = %s
            RETURNING id"""
    dbhelper.run_insert(cur, sql, device, (device['interface'], device['error'], ts))
    dev_db_id = cur.fetchone()[0]
    cur.execute("""UPDATE grafana.device_inserter_state
                SET var_value = %s
                WHERE var_name = 'last_inserted_id'
                AND %s > var_value """, (last_inserted_id, last_inserted_id))
    # committing everything as a single transaction
    #conn.commit()

    smart_attr_nvme = rep.get('nvme_smart_health_information_log')
    if smart_attr_nvme:
        for k, v in smart_attr_nvme.items():
            device_smart_nvme = {}
            device_smart_nvme['device_id'] = dev_db_id
            device_smart_nvme['created']   = ts
            device_smart_nvme['attr_name'] = k
            # FIXME: include list type values, like 'temperature_sensors' (report id 47767)
            if isinstance(v, list):
                print(f"Skipping attr_name: {k} of device report id {r['id']}, attr_val is of type list.\n")
                continue
            if isinstance(v, dict):
                # Checking numeric value is similar to its string
                if 'n' in v:
                    if 's' in v:
                        if str(v['n']) == v['s']:
                            device_smart_nvme['attr_val']  = v['n']
                        else:
                            # In Python3 int() behaves like long()
                            device_smart_nvme['attr_val']  = int(v['s'])
                            device_smart_nvme['attr_val_err'] = str(v)
                    else:
                        device_smart_nvme['attr_val']  = v['n']
                else:
                    device_smart_nvme['attr_val'] = -1
                    device_smart_nvme['attr_val_err'] = str(v)
            else:
                device_smart_nvme['attr_val']  = v

            sql = 'INSERT INTO grafana.device_smart_nvme (%s) VALUES %s'
            dbhelper.run_insert(cur, sql, device_smart_nvme)

    # Device's vendor specific extended SMART log page contents
    # Currently all records accidentally have this key, filtering nvme only
    if device['interface'] == 'nvme' and 'nvme_smart_health_information_add_log' in rep:
        data = rep.get('nvme_smart_health_information_add_log', {})
        # 'Device stats' is found in Intel drives
        dev_stats = data.get('Device stats') if data.get('Device stats') else data
        dev_stats_parsed = {}
        if dev_stats:
            for k, v in dev_stats.items():
                parse_nvme_vendor(k, v, dev_stats_parsed)

        # No nested dictionaries at this point
        for k, v in dev_stats_parsed.items():
            device_smart_nvme_vs = {}
            device_smart_nvme_vs['device_id'] = dev_db_id
            device_smart_nvme_vs['created']   = ts
            device_smart_nvme_vs['attr_name'] = k
            device_smart_nvme_vs['attr_val']  = v 

            sql = 'INSERT INTO grafana.device_smart_nvme_vs (%s) VALUES %s'
            dbhelper.run_insert(cur, sql, device_smart_nvme_vs)

    sata_smart_attr = rep.get('ata_smart_attributes')
    if sata_smart_attr:
        for attr in sata_smart_attr.get('table', []):
            device_smart_sata = {}
            device_smart_sata['device_id']    = dev_db_id 
            device_smart_sata['created']      = ts
            device_smart_sata['attr_id']      = attr['id']
            device_smart_sata['attr_name']    = attr['name']
            device_smart_sata['attr_val']     = attr['raw']['value']
            device_smart_sata['attr_val_str'] = attr['raw']['string']
            device_smart_sata['attr_worst']   = attr['worst']

            sql = 'INSERT INTO grafana.device_smart_sata (%s) VALUES %s'
            dbhelper.run_insert(cur, sql, device_smart_sata)

    conn.commit()
    cur.close()

def main():
    start_time = time.time()
    with open(DSN, 'r') as f:
        dsn_str = f.read().strip()

    conn = psycopg2.connect(dsn_str)
    # Create a named server-side cursor
    dict_cur = conn.cursor(name='server_side_cursor', withhold=True, cursor_factory=psycopg2.extras.DictCursor)

    dict_cur.itersize = 10
    dict_cur.execute("""SELECT device_id, report_stamp, report, id 
                    FROM public.device_report 
                    WHERE id > (SELECT var_value 
                                FROM grafana.device_inserter_state 
                                WHERE var_name = 'last_inserted_id')
                    ORDER BY report_stamp
                    """)

    # check for errors
    cnt = 0
    curr_report = None
    try:
        for r in dict_cur:
            cnt += 1
            curr_report = r
            import_report(conn, r)
    except:
        print(f"Exception when processing public.device_report.id={r['id']}\n")
        conn.rollback()
        raise
    finally:
        dict_cur.close()
        conn.close()
        end_time = time.time()
        time_delta = int(end_time - start_time)
        print(f"Processed {cnt} reports in {time_delta} seconds\n")


if __name__ == '__main__':
    sys.exit(main())

