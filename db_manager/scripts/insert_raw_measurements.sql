INSERT INTO {RAW_TABLE_NAME} (
    device_id, group_name, parent_timestamp, parent_timestampMsec,
    measure_name, raw_data, status, measure_timestamp, measure_timestampMsec
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING;
