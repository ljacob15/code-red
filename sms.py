"""Handles SMS messages to and from users."""

import os
import difflib
import flask

from twilio.twiml.messaging_response import MessagingResponse

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

import sql

# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']
API_SERVICE_NAME = 'people'
API_VERSION = 'v1'

app = flask.Flask(__name__)
# Note: A secret key is included in the sample so that it works.
# If you use this code in your application, replace this with a truly secret
# key. See http://flask.pocoo.org/docs/0.12/quickstart/#sessions.
app.secret_key = 'REPLACE ME - this value is here as a placeholder.'


@app.route('/')
def index():
    """Display testing page."""

    return ""


@app.route("/twilio", methods=['GET', 'POST'])
def message_received():
    """Reply to a user via SMS."""
    #from_number = flask.request.values.get('From', None)

    message_body = flask.request.form['Body']
    words = message_body.split(" ")
    phone_number = words[0]
    resp = MessagingResponse()
    connection = sql.connect()

    # Add checks to ensure phone_number is standardized

    if not sql.existing_user(phone_number, connection):
        message = ("Welcome to Lost in Phone! "
                   "Please click the link below to get started: "
                   "http://lostnphoned.com/authorize?phone={}"
                   .format(phone_number))
    else:
        # Load credentials from the database.
        credentials_dict = sql.get_credentials(phone_number, connection)
        credentials = google.oauth2.credentials.Credentials(
            **credentials_dict)

        people = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=credentials)

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
            message = ("Welcome to Lost in Phone! "
                       "Please click the link below to get started: "
                       "http://lostnphoned.com/authorize?phone={}"
                       .format(phone_number))
        except google.auth.exceptions.GoogleAuthError as error:
            print(error)
            message = "An error occurred. Please try again later."
        else:
            # Find the desired person's phone number
            query = " ".join(words[1:]).lower()
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
                        [item.lower() for item in words[1:]],
                        name.lower().split(" ")):
                    word_matches[name] = number
                elif not word_matches and not exact_matches:
                    contacts[name] = number

            if exact_matches:
                message = ""
                count = 0
                for key, value in exact_matches:
                    message += "{}: {}\n".format(key, value)
                    count += 1
                    if count >= 5:
                        break
            elif word_matches:
                message = ""
                count = 0
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

    connection.close()
    resp.message(message)
    return str(resp)


@app.route('/authorize-success')
def authorize_success():
    """Authorization success page."""

    return "Authorization success!"


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
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    # Store the user's phone number (from the request parameter) for the callback to use.
    flask.session['phone_number'] = flask.request.args.get('phone', type=str)

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    """Obtain credentials."""

    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']
    phone_number = flask.session['phone_number']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the database.
    credentials = flow.credentials

    connection = sql.connect()
    sql.add_user(phone_number, credentials, connection)
    connection.close()

    return flask.redirect(flask.url_for('authorize_success'))


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


if __name__ == '__main__':
    # When running locally, disable OAuthlib's HTTPs verification.
    # ACTION ITEM for developers:
    #     When running in production *do not* leave this option enabled.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

    # Specify a hostname and port that are set as a valid redirect URI
    # for your API project in the Google API Console.
    app.run('0.0.0.0', 80)
    # Testing automated deployment.
