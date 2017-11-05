""" Process the user in the database """


import pymysql as sql

# import mysql.connector
# from mysql.connector import errorcode
import random as rand

# database = "mainData"


def process(number):
    """
    before this, get the user phone number, store it as a string,
    and pass it into this function.
    """
    assert type(number) == str, "number must be a string"
    connection = connect()
    with connection.cursor() as cursor:

        # query = ("SELECT * FROM mainData"
        #         "WHERE phoneNumber = %s")

        query = "SELECT * FROM `mainData` WHERE `phoneNumber` = %s "

        cursor.execute(query, (number))

        if cursor == []:
            print("nothing in here")
            return False #user is not yet in database
        else:
            print("something in here")
            return True #user is already in database


def connect():
    """Connect to the database. Returns connection object."""

    return sql.connect(user='root',
                       password='CodeRed#2017',
                       database='mydatabase',
                       host='129.158.66.189',
                       cursorclass=sql.cursors.DictCursor)

    # except mysql.connector.Error as err:
    #     if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
    #         print("Something is wrong with your user name or password")
    #     elif err.errno == errorcode.ER_BAD_DB_ERROR:
    #         print("Database does not exist")
    #     else:
    #         print(err)


def validate_passphrase(number, public_key, password_attempt):
    # query = ("SELECT security FROM mainData"
    #         "WHERE phoneNumber = %s")

    query = "SELECT security FROM `mainData` WHERE `phoneNumber` = %s "

    cursor.execute(query, (number))

    private_key = cursor

    if private_key * public_key == password_attempt:
        return True
    else:
        return False


def get_token(number):
    # query = ("SELECT token FROM mainData"
    #         "WHERE phoneNumber = %s")

    query = "SELECT token FROM `mainData` WHERE `phoneNumber` = %s "

    cursor.execute(query, (number))

    return cursor


def main(number):
    if process(number):
        print("New user! Proceed to authentication.")
        # EXECUTE AUTHENTICATION
        # token = prompt_for_authentication()

        # REQUEST USER PRIVATE KEY
        #key = request_user_private_key()

        #create user profile in database
        add = "INSERT INTO `mainData` VALUES (%s,%s,%s)"
        # add_new_user = ("INSERT INTO mainData VALUES (%s, %s, %s)")

        cursor.execute(add,(number, token, key))

    else:
        tries = 5
        while (tries > 0):
            print("Welcome back! Here's a public key to combine with your function.")

            # SEND THE PUBLIC KEY TO THE USER, PROMPT FOR PASSWORD

            public_key = rand.randint(100, 999)

            # password_attempt = get_passphrase()

            if validate_passphrase(number, public_key, password_attempt):
                print("Correct! Which contact's number would you like?")

                # PROMPT FOR CONTACT NAME

                # DO SOMETHING WITH THE GOOGLE API
                break

            else:
                tries -= 1
                print("Incorrect password; please try again.")
                # REPROMPT FOR PASSWORD


# main()
process("2149309094")
