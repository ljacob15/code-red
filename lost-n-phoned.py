from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.oauth2.credentials
import google_auth_oauthlib.flow

app = Flask(__name__)

def google_link():
        # Use the client_secret.json file to identify the application requesting
        # authorization. The client ID (from that file) and access scopes are required.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        'https://www.googleapis.com/auth/contacts.readonly')

    # Indicate where the API server will redirect the user after the user completes
    # the authorization flow. The redirect URI is required.
    flow.redirect_uri = 'https://www.google.com'

    # Generate URL for request to Google's OAuth 2.0 server.
    # Use kwargs to set optional request parameters.
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    return authorization_url

@app.route("/", methods=['GET', 'POST'])
def message_received():
    # from_number = request.values.get('From', None)
	# Check if from_number is already in the database
    # If not, add them and get contacts from them

    resp = MessagingResponse()
    message = ("Please click the link below: " + str(google_link()))
    resp.message(message)

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
