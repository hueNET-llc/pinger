# pinger #
A tool to measure ICMP latency

### Requirements ###
- ClickHouse - (fast) Metrics storage
- fping - Measuring ICMP targets

## Environment Variables ##
A sample env can be found in `examples/example.env`

Log Levels: 10/debug, 20/info, 30/warning, 40/error

|  Name  | Description | Type | Default | Example |
| ------ | ----------- | ---- | ------- | ------- |
| HOST_NAME | Host name | str | N/A | router.nyc01 |
| LOG_LEVEL | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) (optional) | str | INFO | INFO |
| DATA_QUEUE_LIMIT | ClickHouse insert queue max length (optional) | int | 50 | 1000 |
| ICMP_INTERVAL| Wait time in between ICMP measurements in seconds (optional) | int | 0 | 10 |
| FPING_NUM_PINGS | Number of ICMP pings to send during each run (optional) | int | 5 | 10 |
| FPING_BACKOFF_FACTOR | Retry backoff factor after failed pings (optional) | int | 1 | 15 |
| FPING_RETRIES | Number of times to retry a failed ping (optional) | int | 1 | 5 |
| FPING_MIN_INTERVAL | Minimum interval in between pings in milliseconds (optional) | int | 100 | 500 |
| CLICKHOUSE_URL | ClickHouse URL | str | N/A | https://192.168.0.5:8123 |
| CLICKHOUSE_USERNAME | ClickHouse username | str | N/A | pinger |
| CLICKHOUSE_PASSWORD | ClickHouse password | str | N/A | hunter2 |
| CLICKHOUSE_DATABASE | ClickHouse database | str | N/A | metrics |
| CLICKHOUSE_TABLE | ClickHouse table (optional) | str | pinger | pinger |

## Targets ##
Target configuration is done via JSON in `targets.json`

A sample configuration can be found in `examples/targets-example.json`

The file layout is as follows:
```
{
    "targets": [
        {
            "name": "target name",
            "ip": "target ip"
        }        
    ]
}
```