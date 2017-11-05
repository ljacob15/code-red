"""Connect to the database."""

import mysql.connector
from mysql.connector import errorcode

def connect():
    """Connect to the database. Returns connection object."""
    try:
        return mysql.connector.connect(user='root',
                                       password='CodeRed#2017',
                                       database='mydatabase',
                                       host='129.158.66.189')

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)

def process_number():
    cnx = connect()
