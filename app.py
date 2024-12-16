from quart import Quart, render_template, make_response, jsonify
from quart_cors import cors  # Import CORS to handle Cross-Origin Resource Sharing
import hypercorn.asyncio
from hypercorn.config import Config
import asyncio
import os
import ssl

# Initialize the Quart app
app = Quart(__name__)

# Enable CORS for all routes (allow cross-origin requests)
app = cors(app, allow_origin="*")

# Define a route for the homepage
@app.route('/')
async def home():
    return await render_template('index.html')

# You can also define additional routes here if needed (like /videos, etc.)

if __name__ == '__main__':
    # Set SSL context with certificate and key files

    # Configure Hypercorn server for HTTP/2 and SSL
    config = Config()
    config.bind = ["localhost:8000"]  # Bind to localhost and port 8000
    config.alpn_protocols = ["h2", "http/1.1"]  # Enable HTTP/2 and HTTP/1.1
    config.certfile = 'cert/cert.pem' # Path to SSL certificate
    config.keyfile = 'cert/key.pem'   # Path to SSL key

    # Run Hypercorn with SSL support
    print("Starting the app with HTTPS and HTTP/2...")
    asyncio.run(hypercorn.asyncio.serve(app, config))
