"""Handles SMS messages to and from users."""

import os
import difflib
import uuid
import flask
import phonenumbers
import schedule

from twilio.twiml.messaging_response import MessagingResponse

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

from lostnphoned import app
from lostnphoned import sql

# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = os.path.join(app.instance_path, "client_secret.json")

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']
API_SERVICE_NAME = 'people'
API_VERSION = 'v1'


@app.before_request
def before_request_callback():
    """Tasks that are run when any request is made,
    before the callback function is run."""
    schedule.run_pending()


@app.route("/twilio", methods=['GET', 'POST'])
def message_received():
    """Reply to a user via SMS."""

    message_body = flask.request.form['Body']
    words = message_body.split(" ")
    resp = MessagingResponse()
    connection = sql.connect()
    from_number = flask.request.values.get('From', None)

    if sql.get_client_attempts(from_number, connection) > 1:
        print("Ignoring message from banned client.")
        return ""

    if words[0].lower() == "register":
        phone_number_obj = get_phone_number_obj(from_number)

        if phone_number_obj:
            phone_number_e164 = phonenumbers.format_number(
                phone_number_obj,
                phonenumbers.PhoneNumberFormat.E164
            )
            if sql.existing_user(phone_number_e164, connection):
                message = "This phone number has already been registered."
            else:
                # Remove old ID from database if it's there (user wants a new URL)
                sql.remove_register_id(phone_number_e164, connection)

                # Generate unique ID
                clientid = generate_clientid()

                # Add ID to database
                sql.add_register_id(clientid, phone_number_e164, connection)

                message = (
                    "Welcome to Lost-n-Phoned! "
                    "To create your account, please click the link and "
                    "allow Lost-n-Phoned access to your Google contacts.\n"
                    "After authorizing with Google, you will receive "
                    "additional instructions on how to add a password. {}"
                    .format(
                        flask.url_for('authorize', clientid=clientid, _external=True)
                    )
                )
        else:
            message = "Lost-n-Phoned could not determine your phone number."
    elif words[0].lower() == "add":
        phone_number_obj = get_phone_number_obj(from_number)

        if phone_number_obj:
            phone_number_e164 = phonenumbers.format_number(
                phone_number_obj,
                phonenumbers.PhoneNumberFormat.E164
            )
            if not sql.existing_user(phone_number_e164, connection):
                message = ("This phone number has not been registered "
                           "with Lost-n-Phoned.")
            elif len(words) == 1 or words[1] == "":
                message = "You did not specify a password to add."
            else:
                sql.add_password(phone_number_e164, words[1], connection)
                message = "Password added."
        else:
            message = "Lost-n-Phoned could not determine your phone number."
    else:
        phone_number_obj = get_phone_number_obj(words[0])

        if phone_number_obj:
            phone_number_e164 = phonenumbers.format_number(
                phone_number_obj,
                phonenumbers.PhoneNumberFormat.E164
            )
            if not sql.existing_user(phone_number_e164, connection):
                message = ("The phone number provided has not been "
                           "registered with Lost-n-Phoned.")
            elif len(words) < 3 or words[1] == "" or words[2] == "":
                message = "You are missing either a password or a name to search."
            elif not sql.password_match(phone_number_e164, words[1], connection):
                sql.increment_client_attempts(from_number, connection)
                # Don't care if from_number isn't valid, use whatever Twilio gives
                message = "Incorrect password."
            else:
                sql.remove_password(phone_number_e164, words[1], connection)
                message = query_contacts(phone_number_e164, words[2:], connection)
        else:
            message = ("Visit https://lostnphoned.com/ "
                       "to learn how to use this service.")

    connection.close()
    resp.message(message)
    return str(resp)


def generate_clientid() -> str:
    """Create a unique ID for the client using UUID."""
    base16 = uuid.uuid4()
    return int_to_base58(base16.int) # pylint: disable=E1101


def int_to_base58(num: int) -> str:
    """Convert an int to a base58 string."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    converted = ""
    while num:
        num, digit = divmod(num, 58)
        converted += alphabet[digit]
    return converted[::-1]


@app.route('/authorize')
def authorize():
    """Authorization link."""

    connection = sql.connect()
    clientid = flask.request.args.get('clientid', type=str)
    if not clientid or not sql.get_register_number(clientid, connection):
        return "Error: Invalid link or link expired."

    # Get phone number corresponding to the clientid from the database
    phone_number_e164 = sql.get_register_number(clientid, connection)

    # Remove the link immediately to prevent the user from clicking the
    # link multiple times and potentially getting through OAuth multiple
    # times.
    sql.remove_register_id(phone_number_e164, connection)

    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true',
        # Get a refresh token even if user has somehow authorized before.
        # In that case, either Lost-n-Phoned has lost the refresh token or
        # the user is registering another phone number with the same Google
        # account. Doing so could disable the user's previously registered
        # number because that number's associated refresh_token may be
        # invalidated by Google.
        prompt='consent')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    # Store the user's phone number (from the request parameter) for the callback to use.
    flask.session['phone_number'] = phone_number_e164
    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    """Obtain credentials."""

    if flask.request.args.get('error', False):
        return flask.redirect('/')

    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']
    phone_number_e164 = flask.session['phone_number'] # Guaranteed to be in E164

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    # I don't think it's possible for the user to already be registered,
    # but just in case...
    connection = sql.connect()
    sql.remove_user(phone_number_e164, connection) # No error if user doesn't exist

    # Store credentials in the database.
    sql.add_user(phone_number_e164, credentials, connection)
    connection.close()

    return flask.redirect('/authorize-success')


def get_phone_number_obj(phone_number):
    """Returns phonenumbers.PhoneNumber object if possible,
    or None if the input could not possibly be a phone number."""
    try:
        phone_number_obj = phonenumbers.parse(phone_number, region="US")
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_possible_number(phone_number_obj):
        return None

    return phone_number_obj


def query_contacts(phone_number, query, connection):
    """Return the user's desired contact in a message."""

    # Load credentials from the database.
    credentials_dict = sql.get_credentials(phone_number, connection)
    credentials = google.oauth2.credentials.Credentials(
        **credentials_dict)

    people = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials,
        cache_discovery=False)

    # Save credentials back to database in case access token was refreshed.
    sql.update_user(phone_number, credentials, connection)

    try:
        results = people.people().connections().list(
            resourceName='people/me',
            pageSize=2000,
            personFields='names,phoneNumbers').execute()
    except google.auth.exceptions.RefreshError:
        print("Expired token error encountered. Removing user.")
        sql.remove_user(phone_number, connection)
        message = ("Welcome to Lost-n-Phoned! "
                   "Please click the link below to get started: "
                   "http://lostnphoned.com/authorize?phone={}"
                   .format(phone_number))
    except google.auth.exceptions.GoogleAuthError as error:
        print(error)
        message = "An error occurred. Please try again later."
    else:
        message = search_contacts(query, results)

    return message


def search_contacts(words, results):
    """Find the desired contact's phone number."""

    query = " ".join(words).lower()
    exact_matches = []
    word_matches = {}
    contacts = {}
    for person in results['connections']:
        try:
            name = person['names'][0]['displayName']
            number = person['phoneNumbers'][0]['value']
        except KeyError:
            continue

        if query == name.lower():
            exact_matches.append((name, number))
        elif not exact_matches and sublist(
                [item.lower() for item in words],
                name.lower().split(" ")):
            word_matches[name] = number
        elif not word_matches and not exact_matches:
            contacts[name] = number

    message = ""
    count = 0
    if exact_matches:
        for key, value in exact_matches:
            message += "{}: {}\n".format(key, value)
            count += 1
            if count >= 5:
                break
    elif word_matches:
        for key, value in word_matches.items():
            message += "{}: {}\n".format(key, value)
            count += 1
            if count >= 5:
                break
    else:
        lowered = {name.lower():name for name in contacts}
        names = difflib.get_close_matches(query, lowered.keys(), cutoff=0.33)
        if names:
            message = "Contact not found. Similar results:\n"
            for name in names:
                message += "{}: {}\n".format(lowered[name], contacts[lowered[name]])
        else:
            message = "Contact not found."

    return message


def sublist(ls1, ls2):
    # modified from https://stackoverflow.com/a/35964184
    '''
    >>> sublist([], [1,2,3])
    False
    >>> sublist([1,2,3,4], [2,5,3])
    True
    >>> sublist([1,2,3,4], [0,3,2])
    False
    >>> sublist([1,2,3,4], [1,2,5,6,7,8,5,76,4,3])
    False
    '''
    def get_all_in(one, another):
        """Get elements shared by both lists."""
        for element in one:
            if element in another:
                yield element

    match = False
    for elem1, elem2 in zip(get_all_in(ls1, ls2), get_all_in(ls2, ls1)):
        if elem1 != elem2:
            return False
        match = True

    return match
