# pinger #
A tool to measure target latency

Log Levels: 10/debug, 20/info, 30/warning, 40/error

### Requirements ###
```
fping - ICMP targets
```

## Environment Variables ##
A sample env can be found in `examples/example.env`

```
--- Pinger ---
DATA_QUEUE_LIMIT    -   Max number of data waiting to be inserted into ClickHouse at once (default: "50")
ICMP_INTERVAL       -   How long to wait in between ICMP measurements (default: "0")
LOG_LEVEL           -   Logging verbosity (default: "20")

--- Host Info ---
HOST_COUNTRY    -   The host machine's country (e.g. "US")
HOST_STATE      -   The host machine's state (e.g. "NJ")
HOST_CITY       -   The host machine's city (e.g. "Newark")

--- FPing Settings ---
FPING_NUM_PINGS         -   Number of ICMP pings to send during each run (default": "5")
FPING_BACKOFF_FACTOR    -   Retry backoff factor after failed pings (default: "1)
FPING_RETRIES           -   How many times to retry a failed ping (default: "1")
FPING_MIN_INTERVAL      -   Minimum interval in between pings in milliseconds (default: "100")

--- ClickHouse Login Info ---
CLICKHOUSE_URL      -   The ClickHouse URL (e.g. "https://192.168.0.69:8123")
CLICKHOUSE_USER     -   The ClickHouse login username
CLICKHOUSE_PASS     -   The ClickHouse login password
CLICKHOUSE_DB       -   The ClickHouse database
CLICKHOUSE_TABLE    -   The ClickHouse table to insert data into (default: "pinger")
```

## Targets ##
Target configuration is done via JSON in `targets.json`

A sample configuration can be found in `examples/targets-example.json`

The file layout is as follows:
```
{
    "targets": [
        {
            "type": "icmp (other types coming soon)",
            "name": "target name",
            "country": "target country (optional)",
            "state": "target state (optional)",
            "city": "target city (optional)",
            "asn": "target asn (optional)",
            "ip": "target ip"
        }        
    ]
}
```