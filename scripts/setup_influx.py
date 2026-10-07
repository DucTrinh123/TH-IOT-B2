import sys
from pathlib import Path

# Allow `python scripts/setup_influx.py` without installing this project as a package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from influxdb_client import InfluxDBClient
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
from iot_pipeline.config import Settings

cfg = Settings()
with InfluxDBClient(url=cfg.influx_url, token=cfg.influx_token, org=cfg.influx_org) as client:
    org = client.organizations_api().find_organizations(org=cfg.influx_org)[0]
    api = client.buckets_api()
    if api.find_bucket_by_name(cfg.processed_bucket) is None:
        api.create_bucket(bucket_name=cfg.processed_bucket, org_id=org.id,
            retention_rules=BucketRetentionRules(type="expire", every_seconds=30 * 86400))
        print(f"Created {cfg.processed_bucket} with 30-day retention")
    else: print(f"Bucket {cfg.processed_bucket} already exists")

