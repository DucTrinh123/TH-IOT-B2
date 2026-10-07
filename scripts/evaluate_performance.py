import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from influxdb_client import InfluxDBClient
from iot_pipeline.config import Settings

def numeric_values(series):
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return clean[clean >= 0]

def main():
    parser = argparse.ArgumentParser(description="Generate IoT latency/storage performance report")
    parser.add_argument("--range", default="-24h", dest="time_range")
    parser.add_argument("--output", default="outputs/performance_report.md")
    args = parser.parse_args(); cfg = Settings()
    query = f'''from(bucket: "{cfg.raw_bucket}")
      |> range(start: {args.time_range})
      |> filter(fn: (r) => r._measurement == "pipeline_metrics")
      |> pivot(rowKey:["_time", "device_id", "status"], columnKey:["_field"], valueColumn:"_value")'''
    with InfluxDBClient(url=cfg.influx_url, token=cfg.influx_token, org=cfg.influx_org) as client:
        frames = client.query_api().query_data_frame(query)
    data = pd.concat(frames, ignore_index=True) if isinstance(frames, list) and frames else frames
    if data is None or data.empty:
        raise SystemExit("No pipeline_metrics data found. Keep collector running and try again.")
    data["_time"] = pd.to_datetime(data["_time"], utc=True)
    accepted = data[data["status"] == "accepted"].copy()
    duration_s = max((data["_time"].max() - data["_time"].min()).total_seconds(), 1)
    total_bytes = int(pd.to_numeric(accepted.get("payload_bytes", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    ingest = numeric_values(accepted["ingest_latency_ms"])
    db_write = numeric_values(accepted["db_write_ms"])
    processing = numeric_values(accepted["processing_total_ms"])
    rows = {
        "Total messages": len(data), "Accepted": len(accepted),
        "Rejected": int((data["status"] == "rejected").sum()),
        "Duplicates": int((data["status"] == "duplicate").sum()),
        "Observed duration (s)": round(duration_s, 2),
        "Average throughput (msg/s)": round(len(accepted) / duration_s, 4),
        "Payload received (bytes)": total_bytes,
        "Estimated payload rate (bytes/s)": round(total_bytes / duration_s, 2),
        "MQTT ingest minimum (ms)": round(float(ingest.min()), 2) if not ingest.empty else "N/A",
        "MQTT ingest average (ms)": round(float(ingest.mean()), 2) if not ingest.empty else "N/A",
        "MQTT ingest maximum (ms)": round(float(ingest.max()), 2) if not ingest.empty else "N/A",
        "DB write minimum (ms)": round(float(db_write.min()), 2) if not db_write.empty else "N/A",
        "DB write average (ms)": round(float(db_write.mean()), 2) if not db_write.empty else "N/A",
        "DB write maximum (ms)": round(float(db_write.max()), 2) if not db_write.empty else "N/A",
        "Processing average (ms)": round(float(processing.mean()), 2) if not processing.empty else "N/A",
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output.with_suffix(".csv"); data.to_csv(csv_path, index=False)
    lines = ["# IoT pipeline performance report", "", f"Range: `{args.time_range}`", "",
             "| Metric | Value |", "|---|---:|"]
    lines.extend(f"| {name} | {value} |" for name, value in rows.items())
    lines += ["", "Notes:", "", "- MQTT ingest is device timestamp to collector receipt.",
              "- DB write is the synchronous InfluxDB write call duration.",
              "- Payload bytes exclude InfluxDB index/metadata overhead; disk usage must be read from the Docker volume."]
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Created {output} and {csv_path}")

if __name__ == "__main__":
    main()

