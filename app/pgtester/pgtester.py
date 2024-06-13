"""
DB operations
"""

import time
from datetime import datetime, timedelta, timezone
from pgtester.db import get_req_cursor, get_req_ro_cursor
from psycopg2 import OperationalError

def startup_access(app):
    """Log latest DB entry (from prior execution) and add a fresh one"""
    try:
        with app.app_context():
            status = get_db_status()
            if status is not None:
                app.logger.info(status_to_string(status))
            else:
                app.logger.info("Empty database at startup!")

            write_current_time(app.logger)
    except OperationalError as e:
        app.logger.error("Error accessing DB at startup: %s", e)

def periodic_writes_and_reads(app, interval_seconds=1):
    """Thread routine"""
    while True:
        with app.app_context():
            time.sleep(interval_seconds)
            try:
                ts = write_current_time(app.logger)
                status = get_db_status()
                ro_status = get_db_status(ro_access=True)
                if status is not None:
                    delta = ts - status['last_write_ts']
                    if delta != timedelta(0):
                        app.logger.warn("Different timestamp read after write!, delta=%s", delta)
                    app.logger.info(status_to_string(status))
                else:
                    app.logger.warn("Empty response from DB")

                if ro_status is not None:
                    ro_delta = ts - ro_status['last_write_ts']
                    if ro_delta != timedelta(0):
                        app.logger.warn("Different timestamp read (read-only) after write!, delta=%s", ro_delta)
                    app.logger.info(status_to_string(ro_status))
                else:
                    app.logger.warn("Empty response from read-only DB access")
            except OperationalError as e:
                app.logger.error("Error accessing DB: %s", e)

def status_to_string(status):
    """Format string based on DB status"""
    last_write_ts = status['last_write_ts']
    db_server_addr = status['db_server_addr']
    total_writes = status['total_writes']
    return f'Latest timestamp: {last_write_ts} from server {db_server_addr} ({total_writes} entries in DB)'

def get_db_status(ro_access = False):
    """Get last written timestamp and total number of table entries"""
    if ro_access:
        cursor = get_req_ro_cursor()
    else:
        cursor = get_req_cursor()
    cursor.execute(
        'SELECT write_ts as last_write_ts'
        ', (SELECT COUNT(*) FROM test_writes) AS total_writes'
        ', (SELECT inet_server_addr()) AS db_server_addr'
        ' FROM test_writes'
        ' ORDER BY write_ts DESC'
        ' LIMIT 1'
    )
    status = cursor.fetchall()

    if len(status) > 0:
        return status[0]

    return None

def reset_db():
    """Delete all rows"""
    cursor = get_req_cursor()
    cursor.execute(
        'TRUNCATE test_writes'
    )
    cursor.connection.commit()
    return []


def write_current_time(logger=None):
    """Add current timestamp to test table"""
    dt = datetime.now(timezone.utc)

    cursor = get_req_cursor()
    cursor.execute(
        'INSERT INTO test_writes (write_ts) VALUES (%s)', (dt,)
    )
    cursor.connection.commit()

    if logger is not None:
        logger.info('Wrote "%s" to table "test_writes"', dt)

    return dt