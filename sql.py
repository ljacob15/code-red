""" Process the user in the database """

import random
import pymysql


def connect():
    """Connect to the database. Returns connection object."""
    connection = pymysql.connect(host='localhost',
                                 user='MySQL_username_here',
                                 password='',
                                 db='lostnphoned',
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    return connection


def existing_user(number: str, connection) -> bool:
    """Check if a phone number is already in the database.

    Returns True if the number is found, False if not."""
    if not isinstance(number, str):
        raise TypeError

    with connection.cursor() as cursor:

        query = "SELECT * FROM users WHERE phone_number = %s"

        cursor.execute(query, (number))

        data = cursor.fetchall()

        return bool(data)


def get_credentials(number: str, connection) -> dict:
    """Retrieve the credentials associated with a user's phone number."""

    with connection.cursor() as cursor:

        query = ("SELECT token, "
                 "refresh_token, "
                 "token_uri, "
                 "client_id, "
                 "client_secret, "
                 "scopes "
                 "FROM users WHERE phone_number = %s")

        cursor.execute(query, (number))

        return cursor.fetchone()


def add_user(number: str, credentials, connection):
    """Add a user's phone number to the database."""
    with connection.cursor() as cursor:

        command = ("INSERT INTO users "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s)")

        data = [number,
                credentials.token,
                credentials.refresh_token,
                credentials.token_uri,
                credentials.client_id,
                credentials.client_secret,
                credentials.scopes]

        cursor.execute(command, data)
        connection.commit()


def update_user(number: str, credentials, connection):
    """Update a user's credentials."""
    with connection.cursor() as cursor:

        data = credentials_to_dict(credentials)
        data['number'] = number

        command = ("UPDATE users "
                   "SET token = %(token)s, "
                   "refresh_token = %(refresh_token)s, "
                   "token_uri = %(token_uri)s, "
                   "client_id = %(client_id)s, "
                   "client_secret = %(client_secret)s, "
                   "scopes = %(scopes)s "
                   "WHERE phone_number = %(number)s")

        cursor.execute(command, data)
        connection.commit()


def remove_user(number: str, connection):
    """Remove a user from the database."""
    with connection.cursor() as cursor:

        command = "DELETE FROM users WHERE phone_number = %s"

        cursor.execute(command, (number))
        connection.commit()


def validate_passphrase(number, public_key, password_attempt, connection):
    # query = ("SELECT security FROM mainData"
    #         "WHERE phone_number = %s")

    assert type(public_key) == int and type(password_attempt) == int, "numerical inputs are not ints!"
    with connection.cursor() as cursor:

        query = "SELECT security FROM `mainData` WHERE `phone_number` = %s "

        cursor.execute(query, (number))

        private_key = int(cursor.fetchall()[0]['security'])
        # print(private_key)

        # print("ANSWER: " + str(private_key * public_key))
        # print("YOUR ANSWER: " + str(password_attempt))

        if (private_key * public_key) == password_attempt:
            return True
        else:
            return False


def credentials_to_dict(credentials):
    """Convert credentials to dictionary format."""

    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


def main(number):
    assert type(number) == str, "number input is not a string"
    connection = connect()
    # print(connection)

    # NEW USER CASE
    if not process(number, connection):
        process_new_user(number, connection)

    # RETURNING USER CASE
    else:
        tries = 5
        print("Welcome back! Here's a public key to combine with your function.")
        while (tries > 0):

            # SEND THE PUBLIC KEY TO THE USER, PROMPT FOR PASSWORD
            public_key = int(random.randint(100, 999))
            print(public_key)

            # password_attempt = get_passphrase()
            password_attempt = int(input("Enter the passphrase by combining the private and public keys."))
            # print("you attempted" + str(password_attempt))

            if validate_passphrase(number, public_key, password_attempt, connection):
                print("Correct!")
                print("Which contact's number would you like?")

                # PROMPT FOR CONTACT NAME
                # DO SOMETHING WITH THE GOOGLE API
                break

            else:
                if (tries == 0):
                    print("Sorry, too many failed attempts")
                    break;
                else:
                    tries -= 1
                    print("Incorrect password; please try again.")
    print("Full program completed. Goodbye.")
