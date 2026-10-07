# IoT pipeline performance report

Range: `-24h`

| Metric | Value |
|---|---:|
| Total messages | 29 |
| Accepted | 29 |
| Rejected | 0 |
| Duplicates | 0 |
| Observed duration (s) | 429.48 |
| Average throughput (msg/s) | 0.0675 |
| Payload received (bytes) | 5065 |
| Estimated payload rate (bytes/s) | 11.79 |
| MQTT ingest minimum (ms) | 54.0 |
| MQTT ingest average (ms) | 50068.04 |
| MQTT ingest maximum (ms) | 97499.0 |
| DB write minimum (ms) | 6.18 |
| DB write average (ms) | 53.62 |
| DB write maximum (ms) | 92.08 |
| Processing average (ms) | 402.88 |

Notes:

- MQTT ingest is device timestamp to collector receipt.
- DB write is the synchronous InfluxDB write call duration.
- Payload bytes exclude InfluxDB index/metadata overhead; disk usage must be read from the Docker volume.
