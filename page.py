import os
from flask import Flask, request, redirect, jsonify
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
import json
import requests

app = Flask(__name__)
port=5000
# OAuth2 scopes
scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

# Dropbox URL for the credential file
DROPBOX_URL = "https://www.dropbox.com/scl/fi/fgeugh1gmmrv4g2dljqam/cred.json?rlkey=pqkw9e9btl0wada3eqy1jjpnt&st=3ghixf37&dl=1"  # Replace with your Dropbox shared link

# Redirect URI
redirect_uri = "https://gmail-server-page.onrender.com/oauth2callback"  # Replace with your deployed Render URL


def get_credential_from_dropbox(dropbox_url):
    """
    Fetch the credential JSON file from Dropbox using the URL and return a flow object.
    """
    response = requests.get(dropbox_url)

    if response.status_code == 200:
        try:
            # Parse the JSON from Dropbox response
            json_data = response.json()  # Ensure Dropbox URL directly serves the JSON

            # Create Flow using the fetched JSON
            flow = Flow.from_client_config(json_data, scopes=scopes)
            return flow
        except Exception as e:
            raise Exception(f"Error parsing the credential JSON: {e}")
    else:
        raise Exception(f"Failed to fetch credentials from Dropbox. Status code: {response.status_code}")


@app.route('/')
def index():
    return "OAuth2 Authorization Server"


@app.route('/authorize')
def authorize():
    try:
        # Fetch credentials from Dropbox and initialize the flow
        flow = get_credential_from_dropbox(DROPBOX_URL)
        flow.redirect_uri = redirect_uri
        
        # Generate the authorization URL
        authorization_url, state = flow.authorization_url(prompt="consent")
        return redirect(authorization_url)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/oauth2callback')
def oauth2callback():
    # This route handles the redirect from Google after the user grants consent
    code = request.args.get('code')
    if not code:
        return "Error: No code found in the request.", 400

    try:
        # Fetch credentials from Dropbox and initialize the flow
        flow = get_credential_from_dropbox(DROPBOX_URL)
        flow.redirect_uri = redirect_uri

        # Exchange the authorization code for an access token
        flow.fetch_token(authorization_response=request.url)

        # Now you have the credentials, you can use them to make API calls
        credentials = flow.credentials

        # Optionally, store the credentials in a secure storage (e.g., a database or file)
        with open("token.json", "w") as token_file:
            token_file.write(credentials.to_json())

        return jsonify({
            "message": "Authorization successful! You can now use the credentials.",
            "credentials": credentials.to_json()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
