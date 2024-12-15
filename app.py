from flask import Flask, render_template, make_response, jsonify
from flask_cors import CORS  # Import CORS to handle Cross-Origin Resource Sharing
import hypercorn.asyncio
from hypercorn.config import Config
import asyncio
import os

# Initialize the Flask app
app = Flask(__name__)

# Enable CORS for all routes (allow cross-origin requests)
CORS(app, origins="*", methods=["GET", "POST"], supports_credentials=True)


# Define a route for the homepage
@app.route('/')
def home():
    return render_template('index.html')



# You can also define additional routes here if needed (like /videos, etc.)

if __name__ == '__main__':
    # Set SSL context with certificate and key files
    ssl_context = ('cert/cert.pem', 'cert/key.pem')

    # Configure Hypercorn server for HTTP/2 and SSL
    config = Config()
    config.bind = ["localhost:8000"]  # Bind to localhost and port 8000
    config.alpn_protocols = ["h2", "http/1.1"]  # Enable HTTP/2 and HTTP/1.1
    config.certfile = ssl_context[0]  # Path to SSL certificate
    config.keyfile = ssl_context[1]   # Path to SSL key

    # Ensure the SSL files are present
    if not os.path.exists(ssl_context[0]) or not os.path.exists(ssl_context[1]):
        print("SSL certificate or key file not found.")
        exit(1)

    # Run Hypercorn with SSL support
    print("Starting the app with HTTPS and HTTP/2...")
    asyncio.run(hypercorn.asyncio.serve(app, config))
