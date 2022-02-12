import aiochclient
import aiohttp
import asyncio
import colorlog
import datetime
import json
import logging
import os
import sys

# Host machine info
HOST_COUNTRY = os.environ.get('HOST_COUNTRY')
HOST_STATE = os.environ.get('HOST_STATE')
HOST_CITY = os.environ.get('HOST_CITY')
HOST_ASN = os.environ.get('HOST_ASN')
HOST_NAME = os.environ['HOST_NAME']

# FPing info
# Number of pings to send to each target during a run
FPING_NUM_PINGS = os.environ.get(
    'FPING_NUM_PINGS',
    '5'
)
# Backoff factor on failed pings
FPING_BACKOFF_FACTOR = os.environ.get(
    'FPING_BACKOFF_FACTOR',
    '1'
)
# Retries on failed ping
FPING_RETRIES = os.environ.get(
    'FPING_RETRIES',
    '1'
)
# Minimum interval between pings (in ms)
FPING_MIN_INTERVAL = os.environ.get(
    'FPING_MIN_INTERVAL',
    '100'
)

# ClickHouse info
CLICKHOUSE_URL = os.environ['CLICKHOUSE_URL']
CLICKHOUSE_USER = os.environ['CLICKHOUSE_USER']
CLICKHOUSE_PASS = os.environ['CLICKHOUSE_PASS']
CLICKHOUSE_DB = os.environ['CLICKHOUSE_DB']
CLICKHOUSE_TABLE = os.environ.get('CLICKHOUSE_TABLE', 'pinger_icmp')

# Max number of inserts waiting to be inserted at once
INSERT_QUEUE_LENGTH = int(os.environ.get('INSERT_QUEUE_LENGTH', 50))

# Log level to use
# 10/debug  20/info  30/warning  40/error
LOG_LEVEL = int(os.environ.get('LOG_LEVEL', 20))
log = logging.getLogger('Pinger')


class Pinger:
    def __init__(self):
        # Setup logging
        self._setup_logging()

        self.loop = asyncio.get_event_loop()

        self.icmp_targets = {}
        # Open and read the targets file
        with open('targets.json', 'r') as file:
            try:
                targets = json.loads(file.read())
            except Exception as e:
                log.error(f'Failed to read targets.json: "{e}"')
                exit(1)

        # Parse targets
        for target in targets['targets']:
            try:
                # Check and default to ICMP
                if target.get('type', 'icmp').lower() == 'icmp':
                    self.icmp_targets[target['ip']] = {
                        'name': target['name'],
                        'country': target.get('country'),
                        'state': target.get('state'),
                        'city': target.get('city'),
                        'asn': target.get('asn'),
                        'ip': target['ip']
                    }
                    log.debug(f'Parsed ICMP target "{target["name"]}" with IP "{target["ip"]}"')
                # TODO: more ping types
                # http, dns, etc.
                else:
                    # Unsupported type
                    log.warning(f'Target "{target["name"]}" has an invalid type "{target["type"]}')
            except Exception:
                log.exception(f'Failed to parse target {target}')

        # Queue of data waiting to be inserted into ClickHouse
        self.data_queue = asyncio.Queue()

    def _setup_logging(self):
        """
            Sets up logging colors and formatting
        """
        # Set the logging level
        logging.root.setLevel(LOG_LEVEL)
        # Create a new handler with colors and formatting
        shandler = logging.StreamHandler(stream=sys.stdout)
        shandler.setFormatter(colorlog.LevelFormatter(
            fmt={
                'DEBUG': '{log_color}{asctime} [{levelname}] {message}',
                'INFO': '{log_color}{asctime} [{levelname}] {message}',
                'WARNING': '{log_color}{asctime} [{levelname}] {message}',
                'ERROR': '{log_color}{asctime} [{levelname}] {message}',
                'CRITICAL': '{log_color}{asctime} [{levelname}] {message}',
            },
            log_colors={
                'DEBUG': 'blue',
                'INFO': 'white',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bg_red',
            },
            style='{',
            datefmt='%H:%M:%S'
        ))
        # Add the new handler
        logging.getLogger('Pinger').addHandler(shandler)
        log.debug('Finished setting up logging')

    async def insert(self):
        """
            Gets data from the insert queue and inserts it into ClickHouse
        """
        while True:
            # Get and check data from the queue
            if not (data := await self.data_queue.get()):
                continue

            # Keep trying until the insert succeeds
            while True:
                try:
                    # Insert the data into ClickHouse
                    await self.clickhouse.execute(
                        f"""
                        INSERT INTO {CLICKHOUSE_TABLE} (
                            host_country, host_state, host_city, host_name, host_asn,
                            target_name, target_country, target_state, target_city,
                            target_asn, target_ip, avg_ms, max_ms, min_ms,
                            loss_percent, time
                        ) VALUES
                        """,
                        *data
                    )
                    log.debug(f'Inserted data with timestamp {data[0][-1]}')
                    # Insert succeeded, break the loop and move on
                    break
                except Exception as e:
                    # Insertion failed
                    log.error(f'Insert failed: "{e}"')
                    # Wait before retrying so we don't spam retries
                    await asyncio.sleep(2)

    async def run(self):
        """
            Setup and run the pingers
        """
        # Create a ClientSession that doesn't verify SSL certificates
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        )
        # Create the ClickHouse client
        self.clickhouse = aiochclient.ChClient(
            self.session,
            url=os.environ['CLICKHOUSE_URL'],
            user=os.environ['CLICKHOUSE_USER'],
            password=os.environ['CLICKHOUSE_PASS'],
            database=os.environ['CLICKHOUSE_DB'],
            json=json
        )
        log.debug(f'Using ClickHouse table "{CLICKHOUSE_TABLE}" at "{CLICKHOUSE_URL}"')

        # Run the queue inserter as a task
        asyncio.create_task(self.insert())

        if self.icmp_targets:
            asyncio.create_task(self.ping_icmp())

        self.loop.run_forever()

    async def ping_icmp(self):
        """
           ICMP pinger 
        """
        # Generate fping args
        fping_args = [
            f'-C{FPING_NUM_PINGS}',         # number of pings to send to target, displayed in automation-friendly format
            '-q',                           # quiet, no per-probe msgs, only final summary, no icmp errors
            f'-B{FPING_BACKOFF_FACTOR}',    # backoff factor on failed ping
            f'-r{FPING_RETRIES}',           # retry limit on failed ping (not including 1st try)
            '-4',                           # force ipv4
            f'i{FPING_MIN_INTERVAL}',       # minimum interval between pings to any target (in milliseconds)
        ]
        # Add target IPs to fping args
        for target in self.icmp_targets.values():
            fping_args.append(target['ip'])

        log.info(f'Running ICMP pinger with {len(self.icmp_targets)} target(s) ')
        log.debug(f'fping args: {fping_args}')

        while True:
            try:
                process = await asyncio.subprocess.create_subprocess_exec(
                    'fping',
                    *fping_args,
                    stdin=None,
                    # fping outputs to stderr instead of stdout for some reason
                    stderr=asyncio.subprocess.PIPE,
                    stdout=None
                )
                # Wait for the process to exit and read stderr
                output = await process.stderr.read()
                # Decode stderr output and split by newline
                output = output.decode().splitlines()
            except Exception:
                log.exception('Failed to read fping output')
                # Wait a few seconds before retrying so we don't spam
                # in case of connectivity loss, etc.
                await asyncio.sleep(2)
                continue

            # Data to be inserted to ClickHouse
            data = []

            # Get the current UTC timestamp
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()

            # Parse fping output
            for result in output:
                # Separate the IP from the latency readings
                target, results = result.split(' : ')
                # Separate the latency readings
                results = results.split(' ')
                # Convert valid latency readings to floats
                timings = [float(r) for r in results if r != '-']
                # Get the target info
                target = self.icmp_targets[target.strip()]

                # Check if there were any readings
                if timings:
                    data.append((
                        HOST_COUNTRY, # host country
                        HOST_STATE, # host state
                        HOST_CITY, # host city 
                        HOST_NAME, # host name
                        HOST_ASN, # host ASN
                        target['name'], # target name
                        target['country'], # target country
                        target['state'], # target state
                        target['city'], # target city
                        target['asn'], # target ASN
                        target['ip'], # target IP
                        sum(timings) / len(timings), # avg ms
                        max(timings), # max ms
                        min(timings), # min ms
                        (len([r for r in results if r == '-']) / len(results)) * 100, # loss percent
                        timestamp
                    ))
                else:
                    # No readings, probably 100% packet loss
                    data.append((
                        HOST_COUNTRY, # host country
                        HOST_STATE, # host state
                        HOST_CITY, # host city 
                        HOST_NAME, # host name
                        HOST_ASN, # host ASN
                        target['name'], # target name
                        target['country'], # target country
                        target['state'], # target state
                        target['city'], # target city
                        target['asn'], # target ASN
                        target['ip'], # target IP
                        None, # avg ms
                        None, # max ms
                        None, # min ms
                        (len([r for r in results if r == '-']) / len(results)) * 100, # loss percent
                        timestamp
                    ))

            # Put the data into the data queue
            try:
                self.data_queue.put_nowait(data)
            except asyncio.QueueFull:
                # Ignore and continue if the queue is full
                # (ClickHouse is probably down/overloaded)
                pass


loop = asyncio.new_event_loop()
loop.run_until_complete(Pinger().run())