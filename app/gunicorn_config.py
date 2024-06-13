""" Configuration for Gunicorn
For details, see: https://docs.gunicorn.org/en/stable/configure.html#configuration-file
"""
# pylint: skip-file

workers = 1
wsgi_app = 'pgtester:create_app()'
bind = '0.0.0.0:8080'
raw_env = ["PGTESTER_GUNICORN_LOGGING=True"]