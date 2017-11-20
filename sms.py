"""Handles SMS messages to and from users."""

import os
import json
import difflib
import flask
import requests

from twilio.twiml.messaging_response import MessagingResponse

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

import sql

# The location of the json file that will contain user data.
FILEPATH = 'data.json'

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

    return "" # print_index_table()

@app.route("/twilio", methods=['GET', 'POST'])
def message_received():
    """Reply to a user via SMS."""
    #from_number = flask.request.values.get('From', None)

    message_body = flask.request.form['Body']
    words = message_body.split(" ")
    phone_number = words[0]
    resp = MessagingResponse()

    # Add checks to ensure phone_number is standardized

    with open(FILEPATH, 'r') as savefile:
        savedata = json.load(savefile)

    if phone_number not in savedata:
        message = ("Welcome to Lost in Phone! "
                   "Please click the link below to get started: "
                   "http://lostnphone.com/authorize?phone={}"
                   .format(phone_number))
    else:
        # Load credentials from the save file.
        credentials = google.oauth2.credentials.Credentials(
            **savedata[phone_number])

        people = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=credentials)

        # Save credentials back to save file in case access token was refreshed.
        savedata[phone_number] = credentials_to_dict(credentials)

        try:
            results = people.people().connections().list(
                resourceName='people/me',
                pageSize=2000,
                personFields='names,phoneNumbers').execute()
        except google.auth.exceptions.RefreshError:
            print("Expired token error encountered. Removing user.")
            del savedata[phone_number]
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
            for connection in results['connections']:
                name = connection['names'][0]['displayName']
                number = connection['phoneNumbers'][0]['value']

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
        finally:
            with open(FILEPATH, 'w+') as savefile:
                json.dump(savedata, savefile)

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
    print("authorize state: " + str(state))

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
    print("oauth2callback state: " + str(state) + ' / ' + phone_number)

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the save file.
    credentials = flow.credentials
    with open(FILEPATH, 'r') as savefile:
        savedata = json.load(savefile)

    savedata[phone_number] = credentials_to_dict(credentials)

    with open(FILEPATH, 'w+') as savefile:
        json.dump(savedata, savefile)

    return flask.redirect(flask.url_for('authorize_success'))


@app.route('/revoke')
def revoke():
    """Revoke credentials."""

    if 'credentials' not in flask.session:
        return ('You need to <a href="/authorize">authorize</a> before ' +
                'testing the code to revoke credentials.')

    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    response = requests.post('https://accounts.google.com/o/oauth2/revoke',
                             params={'token': credentials.token},
                             headers={'content-type': 'application/x-www-form-urlencoded'})

    status_code = getattr(response, 'status_code')
    if status_code == 200:
        return 'Credentials successfully revoked.' + print_index_table()
    else:
        return 'An error occurred.' + print_index_table()


@app.route('/clear')
def clear_credentials():
    """Delete credentials."""

    if 'credentials' in flask.session:
        del flask.session['credentials']
        return ('Credentials have been cleared.<br><br>' +
                print_index_table())


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


def credentials_to_dict(credentials):
    """Convert credentials to dictionary format."""

    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

def print_index_table():
    """Testing page."""

    return ('<table>' +
            '<tr><td><a href="/test">Test an API request</a></td>' +
            '<td>Submit an API request and see a formatted JSON response. ' +
            '    Go through the authorization flow if there are no stored ' +
            '    credentials for the user.</td></tr>' +
            '<tr><td><a href="/authorize">Test the auth flow directly</a></td>' +
            '<td>Go directly to the authorization flow. If there are stored ' +
            '    credentials, you still might not be prompted to reauthorize ' +
            '    the application.</td></tr>' +
            '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
            '<td>Revoke the access token associated with the current user ' +
            '    session. After revoking credentials, if you go to the test ' +
            '    page, you should see an <code>invalid_grant</code> error.' +
            '</td></tr>' +
            '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
            '<td>Clear the access token currently stored in the user session. ' +
            '    After clearing the token, if you <a href="/test">test the ' +
            '    API request</a> again, you should go back to the auth flow.' +
            '</td></tr></table>')


if __name__ == '__main__':
    try:
        with open(FILEPATH, 'r'):
            pass
    except FileNotFoundError:
        with open(FILEPATH, 'w+') as savefile:
            json.dump({}, savefile)

    # When running locally, disable OAuthlib's HTTPs verification.
    # ACTION ITEM for developers:
    #     When running in production *do not* leave this option enabled.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

    # Specify a hostname and port that are set as a valid redirect URI
    # for your API project in the Google API Console.
    app.run('0.0.0.0', 80)
