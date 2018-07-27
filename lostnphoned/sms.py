"""Handles SMS messages to and from users."""

import os
import difflib
import flask
import phonenumbers

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


@app.route("/twilio", methods=['GET', 'POST'])
def message_received():
    """Reply to a user via SMS."""

    message_body = flask.request.form['Body']
    words = message_body.split(" ")
    phone_number = words[0]
    resp = MessagingResponse()
    connection = sql.connect()

    if words[0].lower() == "register":
        from_number = flask.request.values.get('From', None)
        phone_number_obj = get_phone_number_obj(from_number)

        if phone_number_obj:
            phone_number_e164 = phonenumbers.format_number(
                phone_number_obj,
                phonenumbers.PhoneNumberFormat.E164
            )
            if sql.existing_user(phone_number_e164, connection):
                message = "This phone number has already been registered."
            else:
                message = (
                    "Welcome to Lost-n-Phoned! "
                    "Please click the link below to get started: {}"
                    .format(
                        flask.url_for('authorize', phone=phone_number_e164, _external=True)
                    )
                )
        else:
            message = ("Error: Lost-n-Phoned could not determine "
                       "your phone number.")
    else:
        phone_number_obj = get_phone_number_obj(phone_number)

        if phone_number_obj:
            phone_number_e164 = phonenumbers.format_number(
                phone_number_obj,
                phonenumbers.PhoneNumberFormat.E164
            )
            if not sql.existing_user(phone_number_e164, connection):
                message = ("The phone number provided has not been "
                           "registered with Lost-n-Phoned.")
            elif len(words) == 1 or words[1] == "":
                message = "You did not specify a contact name to search for."
            else:
                message = query_contacts(phone_number_e164, words[1:], connection)
        else:
            message = ("Visit https://lostnphoned.com/ "
                       "to learn how to use this service.")

    connection.close()
    resp.message(message)
    return str(resp)


@app.route('/authorize')
def authorize():
    """Authorization link."""

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

    phone_number = flask.request.args.get('phone', type=str)
    try:
        phone_number_obj = phonenumbers.parse(phone_number)
        # Region is None because the number should already be in E164
    except phonenumbers.NumberParseException:
        return "Error: Invalid phone number."

    if not phonenumbers.is_valid_number(phone_number_obj):
        return "Error: Invalid phone number."

    phone_number_e164 = phonenumbers.format_number(
        phone_number_obj,
        phonenumbers.PhoneNumberFormat.E164
    )

    # Check if phone number is already registered, to prevent
    # SQLite UNIQUE constraint error. This could happen if the user
    # clicks the link multiple times.
    connection = sql.connect()
    if sql.existing_user(phone_number_e164, connection):
        return "Error: You have already registered this phone number."

    flask.session['phone_number'] = flask.request.args.get('phone', type=str)
    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    """Obtain credentials."""

    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']
    phone_number = flask.session['phone_number'] # Guaranteed to be in E164

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    # In case the phone number is already registered, clear the existing
    # database entry to avoid SQLite3 UNIQUE constraint error.
    # If we chose to not store anything, then the user would soon have
    # to reregister from the start because the refresh token in
    # the database has been invalidated, and the entry would be deleted.
    connection = sql.connect()
    sql.remove_user(phone_number, connection) # No error even if number
                                              # isn't in database

    # Store credentials in the database.
    sql.add_user(phone_number, credentials, connection)
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
