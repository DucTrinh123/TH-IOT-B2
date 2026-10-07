# ThingsBoard dashboard configuration

Use the existing device alias and create these widgets.

| Widget | Timeseries key | Unit / purpose |
|---|---|---|
| Value card | `temperature` | °C, latest raw value |
| Value card | `humidity` | %RH, latest raw value |
| Gauge | `distance_cm` | cm, range 2-400 |
| Time-series chart | `temperature`, `humidity`, `distance_cm` | Raw real-time data |
| Time-series chart | `processed_temperature`, `processed_temperature_rolling_mean` | Cleaned versus smoothed temperature |
| Time-series chart | `processed_humidity`, `processed_distance_cm` | Resampled processed data |
| Time-series chart | `latency_ms` | Device-to-collector MQTT latency |
| Value card | `rssi` | dBm, Wi-Fi signal |

Set the real-time window to the last 10 or 30 minutes. Run preprocessing again before
the demo so that the processed series covers the latest raw data.

The processed keys are created only when running:

```powershell
.\.venv\Scripts\python.exe -m iot_pipeline.preprocess --range=-24h --interval=1min
```

