/* weekly_cluster -
     Input: grafana.ts_cluster
     Output: week TIMESTAMP, grafana.ts_cluster.*

     Generates one row per cluster per week. Some clusters report once per day while other reports once per 3 days or week.
     For statistics, we want one report for each cluster for some time window (a week by default).
     TODO: Change the date_trunc(...) to 'floor(extract(epoch from ts) / [time window]'

   weekly_metadata -
     Input: weekly_cluster, grafana.metadata
     Output: week TIMESTAMP, grafana.metadata.*, grafana.ts_cluster.cluster_id

    Generates a row per metadata tuple (entity,attr,value,total) per cluster per week... (Currently filters the specific attr 'ceph_version'
    because it's faster than using the 'where' clause in the outer select.
*/
WITH weekly_cluster AS (
  SELECT
    DISTINCT ON (cluster_id, date_trunc('WEEK', grafana.ts_cluster.ts))
    date_trunc('WEEK', grafana.ts_cluster.ts) AS week,
    *
  FROM
    grafana.ts_cluster
  ORDER BY
    cluster_id, date_trunc('WEEK', grafana.ts_cluster.ts), ts DESC
),
weekly_metadata AS (
  SELECT 
    weekly_cluster.week, grafana.metadata.*, weekly_cluster.cluster_id
  FROM
    grafana.metadata
  INNER JOIN
    weekly_cluster ON weekly_cluster.report_id = grafana.metadata.report_id
  WHERE
    attr='ceph_version'
)
select week, sum(total), value from weekly_metadata group by week, value;
