"""
DB operations
"""

import time
import threading

from datetime import datetime, timedelta, timezone
from pgtester.db import get_req_cursor, get_req_ro_cursor
from psycopg2 import OperationalError

periodic_thread = None
periodic_thread_stop = False

def startup_access(app):
    """Log latest DB entry (from prior execution) and add a fresh one"""
    app.logger.info("Running startup access check...")
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

def start_periodic_thread(app, interval_seconds):
    """Start periodic access checks"""
    global periodic_thread
    global periodic_thread_stop

    if periodic_thread is not None:
        app.logger.error("Trying to start periodic thread when it's already running")
        return
    
    app.logger.info("Starting periodic write/read access thread...")
    periodic_thread_stop = False
    periodic_thread = threading.Thread(target=periodic_writes_and_reads, args=(app, interval_seconds,))
    periodic_thread.start()

def stop_periodic_thread():
    """Stop periodic access checks"""
    global periodic_thread
    global periodic_thread_stop
        
    if periodic_thread is not None:
        periodic_thread_stop = True
        periodic_thread.join()
        periodic_thread = None
    
def periodic_writes_and_reads(app, interval_seconds=1):
    """Thread routine"""
    last_exec_time = datetime.now()
    while not periodic_thread_stop:
        time.sleep(0.1)
        if (datetime.now() - last_exec_time) >= timedelta(seconds=interval_seconds):
            last_exec_time = datetime.now()
            with app.app_context():
                try:
                    ts = write_current_time(app.logger)
                    status = get_db_status()
                    validate_read_status(app, ts, status, "read/write")
                except OperationalError as e:
                    app.logger.error("Error accessing (read/write) DB: %s", e)

                try:
                    ro_status = get_db_status(ro_access=True)
                    validate_read_status(app, ts, ro_status, "read-only")                    
                except OperationalError as e:
                    app.logger.error("Error accessing (read-only) DB: %s", e)

    app.logger.info("Periodic thread terminated")

def validate_read_status(app, ts, status, db_kind):
    """Helper for comparing last read timestamp against last written"""
    if status is not None:
        delta = ts - status['last_write_ts']
        if delta != timedelta(0):
            app.logger.warn("Different timestamp read after write!, delta=%s (%s)", delta, db_kind)
        app.logger.info(status_to_string(status))
    else:
        app.logger.warn("Empty response from (%s) DB", db_kind)

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