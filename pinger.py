import aiochclient
import aiohttp
import asyncio
import colorlog
import datetime
import json
import logging
import os
import signal
import sys
import uvloop
uvloop.install()

log = logging.getLogger('Pinger')


class Pinger:
    def __init__(self, loop):
        # Setup logging
        self.setup_logging()
        # Load environment variables
        self.load_env_vars()

        # Get the event loop
        self.loop = loop

        self.targets = {}
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
                self.targets[target['ip']] = target['name']
                log.debug(f'Parsed target "{target["name"]}" with IP "{target["ip"]}"')
            except Exception:
                log.exception(f'Failed to parse target {target}')

        if not self.targets:
            log.error('No valid targets found')
            exit(1)

        # Queue of data waiting to be inserted into ClickHouse
        self.clickhouse_queue = asyncio.Queue(maxsize=self.data_queue_limit)

        # Event used to stop the loop
        self.stop_event = asyncio.Event()

    def setup_logging(self):
        """
            Sets up logging colors and formatting
        """
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

    def load_env_vars(self):
        """
            Loads environment variables
        """
        # Max number of inserts waiting to be inserted at once
        try:
            self.data_queue_limit = max(int(os.environ.get('DATA_QUEUE_LIMIT', 50)), 1)
        except ValueError:
            log.exception('Invalid DATA_QUEUE_LIMIT passed, must be a number')
            exit(1)

        # How long to wait in between ICMP measurements
        try:
            self.icmp_interval = max(int(os.environ.get('ICMP_INTERVAL', 0)), 0)
        except ValueError:
            log.exception('Invalid ICMP_INTERVAL passed, must be a number')
            exit(1)

        # Log level to use
        # 10/debug, 20/info, 30/warning, 40/error, 50/critical
        try:
            log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
            if log_level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
                raise ValueError
        except ValueError:
            log.critical('Invalid LOG_LEVEL, must be a valid log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
            exit(1)

        # Set the log level
        log.setLevel({'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING, 'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}[log_level])


        try:
            self.host_name = os.environ['HOST_NAME']
        except KeyError:
            log.exception('Missing required env var HOST_NAME not set')
            exit(1)

        # FPing info
        # Number of pings to send to each target during a run
        self.fping_num_pings = os.environ.get(
            'FPING_NUM_PINGS',
            '5'
        )
        # Backoff factor on failed pings
        self.fping_backoff_factor = os.environ.get(
            'FPING_BACKOFF_FACTOR',
            '1'
        )
        # Retries on failed ping
        self.fping_retries = os.environ.get(
            'FPING_RETRIES',
            '1'
        )
        # Minimum interval between pings (in ms)
        self.fping_min_interval = os.environ.get(
            'FPING_MIN_INTERVAL',
            '100'
        )

        # ClickHouse info
        self.clickhouse_url = os.environ['CLICKHOUSE_URL']
        self.clickhouse_username = os.environ['CLICKHOUSE_USERNAME']
        self.clickhouse_password = os.environ['CLICKHOUSE_PASSWORD']
        self.clickhouse_database = os.environ['CLICKHOUSE_DATABASE']
        self.clickhouse_table = os.environ.get('CLICKHOUSE_TABLE', 'pinger')

    async def insert_to_clickhouse(self):
        """
            Gets data from the data queue and inserts it into ClickHouse
        """
        while True:
            # Get and check data from the queue
            if not (data := await self.clickhouse_queue.get()):
                continue

            # Keep trying until the insert succeeds
            while True:
                try:
                    # Insert the data into ClickHouse
                    await self.clickhouse.execute(
                        f"""
                        INSERT INTO {self.clickhouse_table} (
                            host_name, target_name, target_ip,
                            avg_ms, max_ms, min_ms, loss_percent,
                            time
                        ) VALUES
                        """,
                        *data
                    )
                    log.debug(f'Inserted data for timestamp {data[0][0]}/{data[0][-1]}')
                    # Insert succeeded, break the loop and move on
                    break
                except Exception as e:
                    # Insertion failed
                    log.error(f'Insert failed for timestamp {data[0][0]}/{data[0][-1]}: "{e}"')
                    # Wait before retrying so we don't spam retries
                    await asyncio.sleep(2)

    async def ping_targets(self):
        """
           Measure ICMP targets
        """
        # Generate fping args
        fping_args = [
            f'-C{self.fping_num_pings}',        # number of pings to send to target, displayed in automation-friendly format
            '-q',                               # quiet, no per-probe msgs, only final summary, no icmp errors
            f'-B{self.fping_backoff_factor}',   # backoff factor on failed ping
            f'-r{self.fping_retries}',          # retry limit on failed ping (not including 1st try)
            '-4',                               # force ipv4
            f'i{self.fping_min_interval}',      # minimum interval between pings to any target (in milliseconds)
        ]
        # Add target IPs to fping args
        for target in self.targets.keys():
            fping_args.append(target)

        log.info(f'Running pinger with {len(self.targets)} target(s) ')
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
                await asyncio.sleep(self.icmp_interval or 2)
                continue

            # Data to be inserted to ClickHouse
            data = []

            # Get the current UTC timestamp
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()

            # Parse fping output
            for result in output:
                try:
                    # Separate the IP from the latency readings
                    target_ip, results = result.strip().split(' : ')
                    # Strip whitespace from the target IP
                    target_ip = target_ip.strip()
                    # Separate the latency readings
                    results = results.split(' ')
                    # Convert valid latency readings to floats
                    timings = [float(r) for r in results if r != '-']
                    # Get the target info
                    target_name = self.targets[target_ip.strip()]

                    # Check if there were any readings
                    if timings:
                        data.append((
                            self.host_name,
                            target_name,
                            target_ip,
                            sum(timings) / len(timings), # avg ms
                            max(timings), # max ms
                            min(timings), # min ms
                            (len([r for r in results if r == '-']) / len(results)) * 100, # loss percent
                            timestamp
                        ))
                    else:
                        # No readings, probably 100% packet loss
                        data.append((
                            self.host_name,
                            target_name,
                            target_ip,
                            None, # avg ms
                            None, # max ms
                            None, # min ms
                            (len([r for r in results if r == '-']) / len(results)) * 100, # loss percent
                            timestamp
                        ))
                except Exception:
                    log.exception('Failed to parse fping result')

            # Put the data into the data queue
            try:
                self.clickhouse_queue.put_nowait(data)
            except asyncio.QueueFull:
                # Ignore and continue if the queue is full
                # (ClickHouse is probably down/overloaded)
                log.warning(f'Failed to queue timestamp {timestamp} for insertion, insert queue is full')

            # Wait the interval before running again
            await asyncio.sleep(self.icmp_interval)

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
            url=self.clickhouse_url,
            user=self.clickhouse_username,
            password=self.clickhouse_password,
            database=self.clickhouse_database,
            json=json
        )
        log.debug(f'Using ClickHouse table "{self.clickhouse_table}" at "{self.clickhouse_url}"')

        # Run the queue inserter as a task
        asyncio.create_task(self.insert_to_clickhouse())

        # Start pinging the targets
        asyncio.create_task(self.ping_targets())

        # Run forever or until we get SIGTERM'd
        await self.stop_event.wait()

        log.info('Exiting...')
        # Close the ClientSession
        await self.session.close()
        # Close the ClickHouse client
        await self.clickhouse.close()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    pinger = Pinger(loop)

    def sigterm_handler(_signo, _stack_frame):
        """
            Handle SIGTERM
        """
        # Set the event to stop the loop
        pinger.stop_event.set()
    # Register the SIGTERM handler
    signal.signal(signal.SIGTERM, sigterm_handler)

    loop.run_until_complete(pinger.run())
