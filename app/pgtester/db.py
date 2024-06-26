"""Abstract DB operations (hide PostgreSQL details)
"""

import psycopg2
import psycopg2.extras

import click
from flask import current_app, g
from psycopg2.errors import OperationalError  # pylint: disable=no-name-in-module


def get_req_cursor():
    """Get access to the database via a request specific (reusable) cursor """
    # "current_app" is a special object that points to the Flask application
    # handling the request
    #
    # "g" is a special object that is unique for each request.
    # It is used to store data that might be accessed by multiple functions
    # during the request

    if 'db_cur' not in g:
        g.db_cur = get_fresh_cursor()

    return g.db_cur

def get_req_ro_cursor():
    """Get read-only access to the database via a request specific (reusable) cursor """

    if 'db_ro_cur' not in g:
        g.db_ro_cur = get_fresh_ro_cursor()

    return g.db_ro_cur

def close_req_db(e=None):  # pylint: disable=unused-argument
    """Clean-up request specific database connection (if there is one)"""
    db_cur = g.pop('db_cur', None)
    db_ro_cur = g.pop('db_ro_cur', None)

    if db_cur is not None:
        close_cursor_connection(db_cur)

    if db_ro_cur is not None:
        close_cursor_connection(db_ro_cur)


def get_fresh_cursor():
    """Create a new connection and cursor for database access"""
    # https://www.psycopg.org/docs/usage.html#basic-module-usage
    connection = psycopg2.connect(
            dbname=current_app.config['POSTGRES_DB'],
            user=current_app.config['POSTGRES_USER'],
            password=current_app.config['POSTGRES_PASSWORD'],
            host=current_app.config['POSTGRES_HOST'],
            port=current_app.config['POSTGRES_PORT']
        )

    # https://varun-verma.medium.com/use-psycopg2-to-return-dictionary-like-values-key-value-pairs-4d3047d8de1b
    cursor = connection.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    return cursor

def get_fresh_ro_cursor():
    """Create a new connection and cursor for database read-only access"""
    connection = psycopg2.connect(
            dbname=current_app.config['POSTGRES_DB'],
            user=current_app.config['POSTGRES_USER'],
            password=current_app.config['POSTGRES_PASSWORD'],
            host=current_app.config['POSTGRES_RO_HOST'],
            port=current_app.config['POSTGRES_PORT']
        )

    cursor = connection.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    return cursor


def close_cursor_connection(cursor):
    """Close both cursor and its associated connection"""
    connection = cursor.connection
    cursor.close()
    connection.close()


def schema_exists(cursor):
    """Check if the schema has been created in the database"""
    # https://stackoverflow.com/questions/1874113/checking-if-a-postgresql-table-exists-under-python-and-probably-psycopg2
    # (but here ".exists" is used as cursor initialized with real-dict factory)
    cursor.execute("""
        SELECT EXISTS(
            SELECT * FROM information_schema.tables
            WHERE table_name=%s
        )
    """, ('test_writes',))
    result = cursor.fetchone()
    return result['exists']


def init_db(cursor = None):
    """Full init/reset of database"""
    if cursor is None:
        cursor = get_req_cursor()

    cursor.execute('DROP TABLE IF EXISTS test_writes CASCADE')

    cursor.execute("""
        CREATE TABLE test_writes (
            id SERIAL PRIMARY KEY,
            write_ts TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)

    cursor.connection.commit()


@click.command('init-db')
@click.option('--reset', is_flag=True, show_default=True, default=False,
              help="Reset the database if it already exists")
def init_db_command(reset):
    """Check for valid database schema and create if necessary."""
    try:
        cursor = get_fresh_cursor()
        if not schema_exists(cursor) or reset:
            click.echo("Initialized a fresh database")
            init_db(cursor)
        else:
            click.echo("Existing database retained")
        close_cursor_connection(cursor)
    except OperationalError as error:
        click.echo("ERROR: Can't connect to database! Invalid/missing configuration?", err=True)
        click.echo("---", err=True)
        click.echo(error, err=True)
        click.echo("---", err=True)
        raise SystemExit("Can't run without a database connection")  # pylint: disable=raise-missing-from


def init_app(app):
    """Configure Flask hooks"""
    app.teardown_appcontext(close_req_db)
    app.cli.add_command(init_db_command)
