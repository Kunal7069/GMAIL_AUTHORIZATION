from flask import Flask, jsonify, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import os
import requests
import io
import dropbox
import json

app = Flask(__name__)
port=80
# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_email_body(message):
    """Extract and decode the email body."""
    parts = message["payload"].get("parts")
    if not parts:
        data = message["payload"]["body"].get("data")
    else:
        for part in parts:
            if part["mimeType"] == "text/plain": 
                data = part["body"].get("data")
                break
        else:
            data = None 

    if data:
        decoded_body = base64.urlsafe_b64decode(data).decode("utf-8")
        return decoded_body
    return "No body content available."

def get_credential_from_dropbox(dropbox_url):
    """Fetch the credential JSON file from Dropbox using the URL."""
    response = requests.get(dropbox_url)
    
    if response.status_code == 200:
        try:
            # The response should contain a JSON object, not the metadata
            json_data = response.json()  # This should be a dictionary with your credentials
            
            # Now directly pass the json_data (dictionary) to the InstalledAppFlow
            flow = InstalledAppFlow.from_client_config(json_data, SCOPES)
            
            return flow  # Returning the credentials object
            
        except Exception as e:
            raise Exception(f"Error parsing the credential JSON: {e}")
    else:
        raise Exception(f"Failed to fetch credential from Dropbox URL, status code: {response.status_code}")
    
@app.route("/auth", methods=["POST"])
def get_auth_url():
    data = request.get_json()
    
    if 'dropbox_cred_url' not in data:
        return jsonify({"error": "DROPBOX_CRED_URL is required in the request body"}), 400
    
    dropbox_cred_url = data['dropbox_cred_url']
    
    try:
        # Fetch credentials from Dropbox
        flow = get_credential_from_dropbox(dropbox_cred_url)
        
        # Generate the authorization URL
        flow.redirect_uri = "https://auth-code.onrender.com"
        auth_url, _ = flow.authorization_url(prompt="consent")
        
        return jsonify({"auth_url": auth_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/authorize", methods=["POST"])
def authorize_code():
    try:
        body = request.json
        response = requests.get("https://auth-code.onrender.com/latest-code")
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch authorization code from external service."}), 500
        
        data = response.json()
        
        if "authorization_code" not in data:
            return jsonify({"error": "Authorization code not found in the response."}), 400
        
        # Extract the authorization code from the response
        code = data["authorization_code"]
        
        dropbox_cred_url = body['dropbox_cred_url']
        
        # Fetch credentials using the provided Dropbox URL
        flow = get_credential_from_dropbox(dropbox_cred_url)
        flow.redirect_uri = "https://auth-code.onrender.com"
        
        # Fetch the token using the authorization code
        flow.fetch_token(code=code)
        creds = flow.credentials
        creds_json = creds.to_json()
        creds_dict = json.loads(creds_json)  # Convert string to dictionary if required
        
        return jsonify(creds_dict), 201
        

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/emails", methods=["POST"])
def fetch_emails():
    try:
        # Get the token.json content from the request body
        data = request.json
        token_data = data['token_json']  # 'token_json' is the key where the token is passed
        
        # Load the token data into credentials
        creds = Credentials.from_authorized_user_info(token_data)
        
        # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread").execute()
        messages = results.get("messages", [])

        if not messages:
            return jsonify({"message": "No new messages."})

        message_data = []
        for message in messages[:10]:  # Limit to the first 10 messages
            msg = service.users().messages().get(userId="me", id=message["id"]).execute()
            msg_details = {"Message ID": msg['id']}

            for header in msg["payload"]["headers"]:
                if header["name"] == "From":
                    msg_details["From"] = header['value']
                if header["name"] == "Subject":
                    msg_details["Subject"] = header['value']

            body = get_email_body(msg)
            msg_details["Body"] = body

            message_data.append(msg_details)

        return jsonify({"messages": message_data})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
