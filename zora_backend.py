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
import pymongo
from datetime import datetime
from flask_cors import CORS  
import spacy
import threading
import time


app = Flask(__name__)
port = 8000
CORS(app)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

client = pymongo.MongoClient("mongodb+srv://TEST:12345@mubustest.yfyj3.mongodb.net")
db = client["ZORA"]
collection = db["AUTH_CODE"]

nlp = spacy.load("en_core_web_sm")

calendar_synonyms = ["calendar", "date", "open the calendar", "open calendar","calendar app", "open the calendar app", "open calendar app"]
settings_synonyms = ["settings", "setting", "open the settings", "open settings", "open the setting", "open setting",
                    "settings app", "setting app", "open the settings app", "open settings app", "open the setting app", "open setting app"]
youtube_synonyms = ["you tube","youtube", "open the youtube", "open youtube", "youtube app", "open the youtube app"]
playstore_synonyms = ["play store","playstore", "open the playstore", "open playstore", "playstore app", "open the playstore app"]
call_synonyms = ["call", "dial", "make a phone call to", "ring", "place a call to","contacts","contact"]
camera_synonyms = ["open the camera","camera","photo", "launch the camera", "start the camera", "activate the camera", "use the camera"]
message_synonyms=  ["send a message", "send message", "text", "inbox","message","messaging","send a text", "respond", "answer the message", "reply to message"]
email_synonyms=["read the latest mail","read latest mail","read latest email","read latest","read the last mail","read"]
reply_synonyms=['reply','reply to latest mail','reply to latest mail','reply the latest mail','reply latest mail','reply mail','reply the mail','reply the last mail','reply last mail']
subject_mail_synonyms=['subject','read subject']



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
        flow.redirect_uri = "https://zora-backend-zjs0.onrender.com"
        auth_url, _ = flow.authorization_url(prompt="consent")
        
        return jsonify({"auth_url": auth_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/authorize", methods=["POST"])
def authorize_code():
    try:
        body = request.json
        response = requests.get("https://zora-backend-zjs0.onrender.com/latest-code")
        
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

@app.route('/', methods=['GET'])
def handle_oauth_callback():
    """
    Handle OAuth callback with code query parameter
    Supports both GET and POST methods
    """
    # Extract code from query parameters
    code = request.args.get('code')
    
    # Additional parameters you might want to capture
    state = request.args.get('state')
    scope = request.args.get('scope')
    
    # If no code is present, return an error
    if not code:
        return jsonify({
            "status": "error",
            "message": "No authorization code found in the request"
        }), 200
    
    # Get current date and time
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create a document to save
    document = {
        "authorization_code": code,
        "timestamp": current_datetime
    }
    
    # Insert the document into MongoDB collection
    collection.insert_one(document)
    
    # Log the received code (in a real-world scenario, process it securely)
    print("Received Authorization Code:", code)
    
    # Return the code in the response
    return jsonify({
        "status": "success",
        "code": code,
        "timestamp": current_datetime
    }), 200

@app.route('/extract-task', methods=['POST'])
def handle_request():
    # Get the JSON data from the request
    data = request.get_json()
    # Extract the sentence from the request body
    sentence = data.get("sentence")
    
    if not sentence:
        return jsonify({"error": "No sentence provided"}), 400

    result = extract_task(sentence)
    return jsonify(result)

@app.route('/latest-code', methods=['GET'])
def get_latest_code():
    """
    Fetch the latest authorization code from the database
    """
    # Find the latest document based on the timestamp
    latest_code_doc = collection.find_one({}, sort=[("timestamp", pymongo.DESCENDING)])
    
    if latest_code_doc:
        return jsonify({
            "status": "success",
            "authorization_code": latest_code_doc["authorization_code"],
            "timestamp": latest_code_doc["timestamp"]
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "No authorization code found in the database"
        }), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)









