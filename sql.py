""" Process the user in the database """

import pymysql
import pymysql.cursors
import random as rand

# import mysql.connector
# from mysql.connector import errorcode


# database = "mainData"

def connect():
    """Connect to the database. Returns connection object."""

    # return pymysql.connect(user='root',
    #                    password='CodeRed#2017',
    #                    database='mydatabase',
    #                    host='129.158.66.189')


    connection = pymysql.connect(host='129.158.66.189',
                                user='root',
                                password='CodeRed#2017',
                                db='mydatabase',
                                port = 3306,
                                charset ='utf8mb4',
                                cursorclass=pymysql.cursors.DictCursor)
    return connection

    # except mysql.connector.Error as err:
    #     if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
    #         print("Something is wrong with your user name or password")
    #     elif err.errno == errorcode.ER_BAD_DB_ERROR:
    #         print("Database does not exist")
    #     else:
    #         print(err)


def process(number, connection):
    """
    before this, get the user phone number, store it as a string,
    and pass it into this function.
    """
    assert type(number) == str, "number must be a string"

    with connection.cursor() as cursor:

        # query = ("SELECT * FROM mainData"
        #         "WHERE phoneNumber = %s")

        query = "SELECT * FROM `mainData` WHERE `phoneNumber` = %s "

        cursor.execute(query, (number))
        # print("OUTPUT: " + str(cursor.fetchall()))
        res = cursor.fetchall()
        if len(res) == 0:
            print("**** new user ****")
            return False #user is not yet in database
        elif len(res) > 0:
            print("**** returning user ****")
            return True #user is already in database


def get_token(number, connection):
    # query = ("SELECT token FROM mainData"
    #         "WHERE phoneNumber = %s")

    with connection.cursor() as cursor:

        query = "SELECT token FROM `mainData` WHERE `phoneNumber` = %s "

        cursor.execute(query, (number))

        return cursor


def validate_passphrase(number, public_key, password_attempt, connection):
    # query = ("SELECT security FROM mainData"
    #         "WHERE phoneNumber = %s")

    assert type(public_key) == int and type(password_attempt) == int, "numerical inputs are not ints!"
    with connection.cursor() as cursor:

        query = "SELECT security FROM `mainData` WHERE `phoneNumber` = %s "

        cursor.execute(query, (number))

        private_key = int(cursor.fetchall()[0]['security'])
        # print(private_key)

        # print("ANSWER: " + str(private_key * public_key))
        # print("YOUR ANSWER: " + str(password_attempt))

        if (private_key * public_key) == password_attempt:
            return True
        else:
            return False


def process_new_user(number, connection):
    with connection.cursor() as cursor:

        print("New user! Proceed to authentication.")
        # EXECUTE AUTHENTICATION
        # token = prompt_for_authentication()
        token = input("What is your gmail username?")


        # REQUEST USER PRIVATE KEY
        key = input("Enter your private key; do not share!")

        number = "\'" + str(number) + "\'"
        token = "\'" + str(token) + "\'"
        key = int(key)
        # print(number)
        # print(token)
        # print(key)

        #create user profile in database
        add = "INSERT INTO `mainData` VALUES ({}, {}, {})".format(number, token, key)
        cursor.execute(add)
        connection.commit()

        print("Added new user")



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
            public_key = int(rand.randint(100, 999))
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

main("1234567890")


# def test_print():
#
    # print(token)
    # print(type(token))
    # foo = token.fetchall()
    # print(foo)
    # print(type(foo))
    #
    # bar = foo[0]
    # print(bar)
    # print(type(bar))
    #
    # baz = bar['token']
    # print(baz)
    # print(type(baz))
