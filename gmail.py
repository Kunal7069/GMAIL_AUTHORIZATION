import base64
import requests
import json
import io
import dropbox
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from flask import Flask, request, jsonify

# Scope for Gmail API
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DROPBOX_ACCESS_TOKEN = "k5RRI0HQU9jFIdQO3Dp32sNnMURnFGRuc8r_Rri298h5uSplHF-P1ATuUI1fQCGVRiDFobDidql9KD5tghHfFJfYfCse9UiIbxpL9C8UAl-UNYJHBiCkQb67mFwaRF5zN-JujYY-1PVJZR3dmTDeZwE8c6bCPaBKapdK4BDOLHMyyo2ySoIVzxzceyf6JZBEH88WjcccTcWBORY77CftpR6m829KjIxY5-6J2wn8JAa4ZsFqu6c-Ps8_hkaLXSUbUKOEHQ6nylkf-zAK12YNBAAZz7RFP9dfDm1JdD8I0ywO05uojQ5LYbDLBinNm9LfQIxjKQV6BkuAWs4Zm9eqvfcxss3Kaylk49gNJ2PBDbR3MjwXkVf8tqO848SfDAE6CqdMtJz4hoicF81xVyT7zIASWscHOhhcksT4serkwa6w5cIp__bpkwGAMRPS5euWmf3AunuzNhW1xrPmAT69_wW-4-JUbiiqvJVHTVx9XLPDEOiCbrIj07W64Oku13khejpd8DdKH7c2hpsCQIMRIzuDUPBTUiQ1Ywh01FhPWEAFGaiJ0A-twq9T6AxlAVu0FB-k4Nl3CvmeewatA6NZq4tOTkCbQkW4QgcUUgjx0Jv1Pm3hHesntm7sH2r1mnlH3WRK24DJGxi5-YzSIe_azA2KihF_KtS8a6DgSTIciKwJNiSWeVrk2nPxuiqW7kjktAevD1FWi68OnNrL3s_Kv_kWBTN4zUchGPz_3GLMEFBPnEZw3FCLOY8H6derj1b3zoxTDo48TuUbhxObAlxnB70ugC8k0-Mthwcqbdq1VLUERqNYmrvSrZD_wfBw_3gn20KNy8pjzhHv8-KlbI94CEpbIy6ajNaJV15dfDqT76AhFbAhnrqo-vUxMylY88fmGijxz0fYnllVtzPJEM5L1SBLshZDOSU2AqaR2Gb3T4DDqEN9nwrfkQpDbKCEy4OF_ip9_8Z26g0lnt6Ct5lIyvuLU-VakLXfJ9YnS540I1U2lxwcYQ1mEWydx2hXm6kQtDA0yK3tvbPebZZ_DsV0RibJHPH0klhR4exh_nvnrje19dgeQOr9Rmlec3n9R_aMkWQkPYVx7aYr118MNBoZTcEURFGI7n9w6urPH6_NRfSASFQKVC4TzPOJ59SHunsK9g7T181aNxN8tZqG7LNlzWpBUF5kHyPYz_KUv3v4Me16WTbaVIhBrp6slO9rwZZXeT-2-5Z614GobE-2z-rwMZSfIJ-EXs-puVy0dH_zfkOMH-XqZBr63u5XvP0rQLgsPKY458oZdg6uIg4ZrluUijIwXJ1Q4qS61Yvzje-lqOiNKxnTF12uTfPYBU6o8YHS8SymYE6nXqX6hsQaaJ7BQ85f-Oqrw9Hf_stxrmXdWw2yRZ6rTtcK04ijDIBDoKB1IXsCH8hctBgmaIKje788q2KYiSKKM8wd2kITK9c10Vb_qrcEYiJA5DFcDAGT_8qy8tIGoFX-QAziuHd-_yVLJXFA.u.ls"
DROPBOX_ACCESS_TOKEN = DROPBOX_ACCESS_TOKEN[::-1]
app = Flask(__name__)

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

def upload_to_dropbox(file_path, file_content):
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

def get_token_from_url(url):
    """Fetch the token file from the URL and return it as a Credentials object."""
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




def get_credential_from_dropbox(dropbox_url):
    """Fetch the credential JSON file from Dropbox using the URL."""
    response = requests.get(dropbox_url)
    
    if response.status_code == 200:
        try:
            # The response should contain a JSON object, not the metadata
            json_data = response.json()  # This should be a dictionary with your credentials
            
            # Now directly pass the json_data (dictionary) to the InstalledAppFlow
            flow = InstalledAppFlow.from_client_config(json_data, SCOPES)
            creds = flow.run_local_server(port=0)
            
            return creds  # Returning the credentials object
            
        except Exception as e:
            raise Exception(f"Error parsing the credential JSON: {e}")
    else:
        raise Exception(f"Failed to fetch credential from Dropbox URL, status code: {response.status_code}")
    

    
@app.route('/gmail', methods=['POST'])
def gmail_api():
    """API endpoint to fetch unread Gmail messages using token from URL."""
    data = request.get_json()

    if 'DROPBOX_URL' not in data:
        return jsonify({"error": "DROPBOX_URL is required in the request body"}), 400
    
    dropbox_url = data['DROPBOX_URL']
    filename = data['filename']
    
    if dropbox_url == "":
        url="https://www.dropbox.com/scl/fi/16g2xj1m1rzqdesm8sci6/credential.json?rlkey=u1r8aygafibzv9agjhocex5lh&st=hrlbvv5k&dl=1"
        creds = get_credential_from_dropbox(url)
        creds_json = creds.to_json()
        dropbox_link = upload_to_dropbox(filename, creds_json)
        return jsonify({"Link": dropbox_link}), 201
        
    creds = get_token_from_url(dropbox_url)
    if creds is None:
        return jsonify({"error": "Failed to fetch token from the URL"}), 400

    try:
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread").execute()
        messages = results.get("messages", [])

        if not messages:
            return jsonify({"message": "No new messages."})

        message_data = []
        for message in messages[:10]:  # Limit to the first 2 messages
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

    except HttpError as error:
        return jsonify({"error": f"An error occurred: {error}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
