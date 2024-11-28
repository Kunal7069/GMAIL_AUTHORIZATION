import os
from flask import Flask, request, redirect, jsonify
from google_auth_oauthlib.flow import Flow
import json

app = Flask(__name__)

# OAuth2 credentials
client_secrets_file = "cred.json"  # Path to your OAuth 2.0 credentials
scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

# The URL for the redirect after authorization
redirect_uri = "https://your-render-url.com/oauth2callback"  # Replace with your deployed Render URL

# Set up the flow for OAuth2
flow = Flow.from_client_secrets_file(client_secrets_file, scopes=scopes)
flow.redirect_uri = redirect_uri


@app.route('/')
def index():
    return "OAuth2 Authorization Server"


@app.route('/authorize')
def authorize():
    # Start the OAuth flow by generating the authorization URL
    authorization_url, state = flow.authorization_url(prompt="consent")
    return redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # This route handles the redirect from Google after the user grants consent
    code = request.args.get('code')
    if not code:
        return "Error: No code found in the request.", 400

    try:
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
    app.run(debug=True, port=5000)
