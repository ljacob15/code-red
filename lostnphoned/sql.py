"""Handles all database functionality."""

import sqlite3
import click
from flask import current_app
from flask.cli import with_appcontext


def init_app(app):
    """Set up module functionalities."""
    app.cli.add_command(init_db_command)


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def init_db():
    """Execute schema.sql."""
    connection = connect()

    with current_app.open_resource('schema.sql') as f:
        connection.executescript(f.read().decode('utf8'))


def connect():
    """Connect to the database. Returns connection object."""
    connection = sqlite3.connect(
        current_app.config['DATABASE'],
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    connection.row_factory = sqlite3.Row
    return connection


def existing_user(number: str, connection) -> bool:
    """Check if a phone number is already in the database.

    Returns True if the number is found, False if not."""

    cursor = connection.cursor()

    query = "SELECT * FROM users WHERE phone_number = ?"

    cursor.execute(query, (number,))

    data = cursor.fetchall()

    return bool(data)


def get_credentials(number: str, connection) -> dict:
    """Retrieve the credentials associated with a user's phone number."""

    cursor = connection.cursor()

    query = ("SELECT token, "
             "refresh_token, "
             "token_uri, "
             "client_id, "
             "client_secret "
             "FROM users WHERE phone_number = ?")

    cursor.execute(query, (number,))

    return cursor.fetchone()


def add_user(number: str, credentials, connection):
    """Add a user's phone number to the database."""
    cursor = connection.cursor()

    command = ("INSERT INTO users "
               "VALUES (?, ?, ?, ?, ?, ?)")

    data = (number,
            credentials.token,
            credentials.refresh_token,
            credentials.token_uri,
            credentials.client_id,
            credentials.client_secret)

    cursor.execute(command, data)
    connection.commit()


def update_user(number: str, credentials, connection):
    """Update a user's credentials."""
    cursor = connection.cursor()

    data = credentials_to_dict(credentials)
    data['number'] = number

    command = ("UPDATE users "
               "SET token = :token, "
               "refresh_token = :refresh_token, "
               "token_uri = :token_uri, "
               "client_id = :client_id, "
               "client_secret = :client_secret "
               "WHERE phone_number = :number")

    cursor.execute(command, data)
    connection.commit()


def remove_user(number: str, connection):
    """Remove a user from the database."""
    cursor = connection.cursor()

    command = "DELETE FROM users WHERE phone_number = ?"

    cursor.execute(command, (number,))
    connection.commit()


def credentials_to_dict(credentials):
    """Convert credentials to dictionary format."""

    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret}
