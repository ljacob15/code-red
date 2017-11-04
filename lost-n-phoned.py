from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def message_received():
    # from_number = request.values.get('From', None)
	# Check if from_number is already in the database
    # If not, add them and get contacts from them

    resp = MessagingResponse()
    resp.message("I received your message!")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
