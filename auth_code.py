from flask import Flask, request, jsonify
import json
import pymongo
from datetime import datetime

app = Flask(__name__)
port = 8000

# MongoDB Atlas connection details
client = pymongo.MongoClient("mongodb+srv://TEST:12345@mubustest.yfyj3.mongodb.net")
db = client["ZORA"]
collection = db["AUTH_CODE"]

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










