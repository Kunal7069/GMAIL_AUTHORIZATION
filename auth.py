from flask import Flask, jsonify, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import requests
import io
import dropbox
import json

app = Flask(__name__)
port=80
# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_token_from_url(url):
    response = requests.get(url)
    
    if response.status_code == 200:
        # Parse the token file content into a Credentials object
        token_data = json.loads(response.text)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        print("Token loaded successfully from URL.")
        return creds
    else:
        print(f"Failed to download the token file, status code: {response.status_code}")
        return None

def upload_to_dropbox(file_path, file_content,DROPBOX_ACCESS_TOKEN):
    """Upload the file to Dropbox and return the shared link URL."""
    dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
    
    # Use in-memory file to avoid creating a physical file on disk
    file_content_bytes = file_content.encode('utf-8')  # Encode the content to bytes
    
    # Upload file to Dropbox using in-memory content
    with io.BytesIO(file_content_bytes) as file_stream:
        dbx.files_upload(file_stream.read(), f'/{file_path}', mode=dropbox.files.WriteMode.overwrite)
    
    # Create a shared link to the file
    shared_link_metadata = dbx.sharing_create_shared_link_with_settings(f'/{file_path}')
    return shared_link_metadata.url

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
        flow.redirect_uri = "https://www.sih.gov.in"
        auth_url, _ = flow.authorization_url(prompt="consent")
        
        return jsonify({"auth_url": auth_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/authorize", methods=["POST"])
def authorize_code():
    try:
        data = request.json
        if "code" not in data:
            return jsonify({"error": "Authorization code is required."}), 400
        filename=data['filename']
        code = data["code"]
        dropbox_access_token = data['dropbox_access_token']
        dropbox_cred_url = data['dropbox_cred_url']
        flow = get_credential_from_dropbox(dropbox_cred_url)
        flow.redirect_uri = "https://www.sih.gov.in"
        flow.fetch_token(code=code)
        
        creds = flow.credentials
        creds_json = creds.to_json()
        dropbox_link = upload_to_dropbox(filename, creds_json,dropbox_access_token)
     
        return jsonify({"Link": dropbox_link}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/emails", methods=["POST"])
def fetch_emails():
    try:
        data = request.json
        dropbox_url=data['dropbox_url']
        creds = get_token_from_url(dropbox_url)
        
        # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)

        # Get the list of message IDs
        results = service.users().messages().list(userId="me", maxResults=10).execute()
        messages = results.get("messages", [])

        if not messages:
            return jsonify({"emails": []}), 200

        # Fetch detailed information for each message
        emails = []
        for message in messages:
            msg = service.users().messages().get(userId="me", id=message["id"]).execute()
            snippet = msg.get("snippet", "")  # Get the email snippet (summary)
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            # Extract useful headers like Subject and From
            email_data = {"snippet": snippet}
            for header in headers:
                if header["name"] == "Subject":
                    email_data["subject"] = header["value"]
                if header["name"] == "From":
                    email_data["from"] = header["value"]
            
            emails.append(email_data)

        return jsonify({"emails": emails}), 200

    except HttpError as error:
        return jsonify({"error": f"An error occurred: {error}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
