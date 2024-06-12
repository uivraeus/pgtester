""" Package configuration
__init__.py serves double duty:
1. it will contain the application factory,
2. it tells Python that the pgtester directory should be treated as a package.
"""

# pylint: disable=import-outside-toplevel

import logging
import os
import threading

from flask import Flask

def create_app(test_config=None):
    """Application Factory function"""
    # create and configure the app
    # (instance path not really used but configure a well-known value just in case)
    app = Flask(__name__, instance_path='/tmp/pgtester-instance')
    app.config.from_mapping(
        # defaults
        SECRET_KEY="dev",  # <-- used for session cookies - replace with actual secret in prod
        POSTGRES_HOST="localhost",
        POSTGRES_PORT="5432",
        POSTGRES_DB="pgtester",
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD="password",
        GUNICORN_LOGGING=False
    )

    # overrides
    if test_config is None:
        # Load all applicable environment variables, e.g. PGTESTER_POSTGRES_PASSWORD="s3cr3t"
        app.config.from_prefixed_env(prefix="PGTESTER")
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # Configure combined logging when app is running behind Gunicorn
    if app.config['GUNICORN_LOGGING']:
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

    # ensure the instance folder exists (if/when needed)
    os.makedirs(app.instance_path, exist_ok=True)

    from . import db
    db.init_app(app)

    from . import pgtester
    
    app.add_url_rule("/reset", view_func=pgtester.reset_db)
    app.add_url_rule("/", view_func=pgtester.get_db_status)
    
    # Check current status and add new entry immediately
    with app.app_context():
        status = pgtester.get_db_status()
        if status is not None:
            app.logger.info(pgtester.status_to_string(status))
        else:
            app.logger.info("Empty database at startup!")

        pgtester.write_current_time()

    # Start periodic writes in the background.
    t = threading.Thread(target=pgtester.periodic_writes, args=(app, 5,))
    t.start()    
    
    app.logger.info("🚀 pgtester app launched! DB config: host=%s:%s, user=%s, db=%s",
        app.config['POSTGRES_HOST'],
        app.config['POSTGRES_PORT'],
        app.config['POSTGRES_USER'],
        app.config['POSTGRES_DB'])

    return app
