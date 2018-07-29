"""Handles all database functionality."""

import os
import hashlib
import sqlite3
import click
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from flask.cli import with_appcontext


def init_app(app):
    """Set up module functionalities."""
    app.cli.add_command(init_db_command)
    scheduler = BackgroundScheduler()
    scheduler.add_job(remove_clients, 'interval', days=1)
    scheduler.start()


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

    # Enable foreign key support
    connection.execute("PRAGMA foreign_keys = ON")
    connection.commit()
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
               "VALUES (?, ?, ?, ?, ?, ?, ?)")

    data = (number,
            credentials.token,
            credentials.refresh_token,
            credentials.token_uri,
            credentials.client_id,
            credentials.client_secret,
            os.urandom(16))

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


def credentials_to_dict(credentials):
    """Convert credentials to dictionary format."""

    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret}


def remove_user(number: str, connection):
    """Remove a user from the database."""
    cursor = connection.cursor()

    command = "DELETE FROM users WHERE phone_number = ?"

    cursor.execute(command, (number,))
    connection.commit()


def add_password(number: str, password: str, connection):
    """Add a password to a user."""

    # Get salt from users table
    cursor = connection.cursor()
    command = "SELECT salt FROM users WHERE phone_number = ?"
    cursor.execute(command, (number,))
    salt = cursor.fetchone()[0]

    # Hash the password with the salt
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)

    # Store password into passwords table
    command = ("INSERT INTO passwords (phone_number, password) "
               "VALUES (?, ?)")
    cursor.execute(command, (number, hashed))
    connection.commit()


def password_match(number: str, password: str, connection):
    """Check if the input matches a password for number.
    Returns a bool."""

    # Get salt from users table
    cursor = connection.cursor()
    command = "SELECT salt FROM users WHERE phone_number = ?"
    cursor.execute(command, (number,))
    salt = cursor.fetchone()[0]

    # Hash the inputted password attempt with the salt
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)

    # Search database for hashed password attempt
    command = ("SELECT * FROM passwords "
               "WHERE phone_number = ? AND password = ?")
    cursor.execute(command, (number, hashed))
    return bool(cursor.fetchone())


def remove_password(number: str, password: str, connection):
    """Remove the given password from the database."""

    # Get salt from users table
    cursor = connection.cursor()
    command = "SELECT salt FROM users WHERE phone_number = ?"
    cursor.execute(command, (number,))
    salt = cursor.fetchone()[0]

    # Hash the inputted password attempt with the salt
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)

    # Search database for hashed password attempt
    command = ("DELETE FROM passwords "
               "WHERE phone_number = ? AND password = ?")
    cursor.execute(command, (number, hashed))
    connection.commit()


def increment_client_attempts(number: str, connection):
    """Increment the number of failed attempts a client has made.
    If the client is not in the database, it is added."""

    cursor = connection.cursor()

    command = ("INSERT OR IGNORE INTO bannable_clients "
               "(phone_number, attempts) VALUES (?, 0)")
    cursor.execute(command, (number,))

    command = ("UPDATE bannable_clients SET attempts = attempts + 1 "
               "WHERE phone_number = ?")
    cursor.execute(command, (number,))

    command = ("UPDATE bannable_clients "
               "SET last_attempt = CURRENT_TIMESTAMP "
               "WHERE phone_number = ?")
    cursor.execute(command, (number,))

    connection.commit()


def get_client_attempts(number: str, connection):
    """Get how many failed attempts a client has made."""

    cursor = connection.cursor()
    command = ("SELECT attempts FROM bannable_clients "
               "WHERE phone_number = ?")
    cursor.execute(command, (number,))

    data = cursor.fetchone()

    if data: # fetchone() could return None
        return data[0]

    return 0


def remove_clients():
    """Remove clients for whom enough time
    has passed from the database ."""

    connection = connect()
    cursor = connection.cursor()
    command = ("DELETE FROM bannable_clients "
               "WHERE last_attempt < DATETIME('now', '-7 days')")
    cursor.execute(command)
    connection.commit()
