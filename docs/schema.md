# Mô tả schema database

Hệ thống sử dụng InfluxDB 2.x vì dữ liệu cảm biến là dữ liệu time-series. Timestamp
của thiết bị được dùng làm thời gian của point; nếu thiết bị chưa đồng bộ NTP thì dùng
thời gian nhận tại gateway.

## 1. Dữ liệu thô

- Bucket: `iot_raw`.
- Retention: 7 ngày.
- Measurement: `sensor_telemetry`.

### Tags

| Tên | Kiểu | Ý nghĩa |
|---|---|---|
| `device_id` | string | Định danh thiết bị, ví dụ `esp32-b23dcat301` |
| `source` | string | Nguồn dữ liệu, hiện là `esp32` |

### Fields

| Tên | Kiểu | Đơn vị | Ý nghĩa |
|---|---|---|---|
| `temperature` | float | °C | Nhiệt độ DHT22 |
| `humidity` | float | %RH | Độ ẩm DHT22 |
| `distance_cm` | float | cm | Khoảng cách HC-SR04 |
| `rssi` | integer | dBm | Cường độ tín hiệu Wi-Fi |
| `sequence` | integer | - | Số thứ tự bản tin trong một lần khởi động |
| `boot_id` | integer | - | Mã ngẫu nhiên của lần khởi động |
| `uptime_s` | integer | giây | Thời gian thiết bị đã hoạt động |
| `latency_ms` | integer | ms | Thời gian từ timestamp thiết bị đến collector |

Khóa logic chống trùng là `(device_id, boot_id, sequence)`. Tags chỉ chứa thuộc tính
có số lượng giá trị hữu hạn; số đo cảm biến được lưu dưới dạng fields để tránh tăng
cardinality của InfluxDB.

## 2. Metric vận hành pipeline

- Bucket: `iot_raw`.
- Measurement: `pipeline_metrics`.

### Tags

| Tên | Ý nghĩa |
|---|---|
| `device_id` | Thiết bị tạo bản tin |
| `status` | `accepted`, `rejected` hoặc `duplicate` |

### Fields

| Tên | Ý nghĩa |
|---|---|
| `payload_bytes` | Kích thước MQTT payload |
| `ingest_latency_ms` | Độ trễ từ thiết bị đến collector |
| `db_write_ms` | Thời gian gọi ghi đồng bộ InfluxDB |
| `processing_total_ms` | Tổng thời gian xử lý một bản tin |
| `throughput_msg_s` | Số bản tin hợp lệ trung bình mỗi giây |
| `accepted_count` | Tổng số bản tin hợp lệ trong phiên collector |
| `rejected_count` | Tổng số bản tin bị từ chối trong phiên |
| `duplicate_count` | Tổng số bản tin trùng trong phiên |

## 3. Dữ liệu đã tiền xử lý

- Bucket: `iot_processed`.
- Retention: 30 ngày.
- Measurement: `sensor_features`.

### Tags

| Tên | Ý nghĩa |
|---|---|
| `device_id` | Thiết bị nguồn; mỗi thiết bị được xử lý riêng |
| `pipeline` | Phiên bản pipeline `iqr-interpolate-resample-zscore` |

### Fields

Với mỗi cảm biến `temperature`, `humidity` và `distance_cm`, measurement lưu:

| Mẫu tên field | Ý nghĩa |
|---|---|
| `<sensor>` | Giá trị đã làm sạch và resampling |
| `<sensor>_rolling_mean` | Trung bình trượt 3 cửa sổ |
| `<sensor>_delta` | Chênh lệch so với cửa sổ trước |
| `<sensor>_zscore` | Giá trị chuẩn hóa Z-score |

Ví dụ: `temperature`, `temperature_rolling_mean`, `temperature_delta`,
`temperature_zscore`.

## 4. Chính sách lưu trữ

Dữ liệu raw chỉ giữ 7 ngày để hạn chế dung lượng vì tần suất ghi cao. Dữ liệu
processed có mật độ thấp hơn sau resampling nên giữ 30 ngày để phục vụ phân tích xu
hướng. InfluxDB tự động xóa point hết hạn theo retention policy của từng bucket.

