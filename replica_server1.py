from quart import Quart, Response, request
import os
import ssl
from quart_cors import cors  # Use quart_cors for CORS support
from hypercorn.asyncio import serve
from hypercorn.config import Config
import asyncio

# Initialize Quart app
app = Quart(__name__)

# Enable CORS for all routes (allow cross-origin requests)
app = cors(app, allow_origin="*")

# Directory to store replicated videos
REPLICA_VIDEO_DIRECTORY = '.replicated_videos_1'

# Path to the CA certificate
# Ensure the replica video directory exists
os.makedirs(REPLICA_VIDEO_DIRECTORY, exist_ok=True)
CA_CERT_PATH = 'cert/cert.pem'


def get_ssl_context():
    """Create and return a unified SSL context."""
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile='cert/cert.pem', keyfile='cert/key.pem')
    ssl_context.load_verify_locations(cafile=CA_CERT_PATH)
    ssl_context.verify_mode = ssl.CERT_OPTIONAL
    return ssl_context
@app.route('/')
async def home():
    """
    Welcome endpoint for the replica server.
    """
    return "Welcome to Replica Server 1!"

@app.route('/<video_name>')
async def serve_replicated_video(video_name):
    """
    Serve a video file from the replica server.

    - HEAD: Check if the video exists and return 200 if it does.
    - GET: Stream the video file if it exists.
    """
    # Sanitize the video name to prevent directory traversal
    video_name = os.path.basename(video_name)
    video_path = os.path.join(REPLICA_VIDEO_DIRECTORY, video_name)

    if os.path.exists(video_path):
        if request.method == 'HEAD':
            # For HEAD requests, only check the existence of the file
            return Response(status=200)
        
        # For GET requests, stream the video file
        return await stream_video(video_path)

    return Response('Video not found', status=404)

@app.route('/replicate', methods=['POST'])
async def replicate_video():
    """
    Handle the video replication from the origin server.
    """
    try:
        # Retrieve video name and file from the request
        form_data = await request.form
        files_data = await request.files

        video_name = form_data.get('video_name')
        video_file = files_data.get('video')

        # Validate input data
        if not video_name:
            print("Error: Missing 'video_name' in the form data.")
            return Response("Missing 'video_name' in the form data.", status=400)
        
        if not video_file:
            print("Error: Missing 'video' file in the request.")
            return Response("Missing 'video' file in the request.", status=400)

        # Sanitize the video name to prevent directory traversal
        video_name = os.path.basename(video_name)
        video_path = os.path.join(REPLICA_VIDEO_DIRECTORY, video_name)

        # Save the uploaded video to the replica server directory
        print(f"Saving video to: {video_path}")
        await video_file.save(video_path)

        print(f"Video {video_name} replicated successfully.")
        return Response(f"Video {video_name} replicated successfully.", status=200)
    
    except Exception as e:
        # Log the error and return a 500 status with the exception details
        print(f"Error during replication: {e}")
        return Response(f"Error during replication: {str(e)}", status=500)

async def stream_video(video_path):
    """Asynchronously stream a video file."""
    def generate():
        try:
            with open(video_path, 'rb') as video_file:
                while chunk := video_file.read(1024 * 64):  # Stream 64 KB chunks
                    yield chunk
        except Exception as e:
            print(f"Error during video streaming: {e}")
            raise e

    return Response(generate(), content_type="video/mp4")

if __name__ == '__main__':
    # Configure the server to use HTTP/2 with SSL and require client certificates
    config = Config()
    config.bind = ["localhost:8081"]  # Set the server to listen on localhost and port 8081
    config.alpn_protocols = ["h2","http/1.1"]  # Enable HTTP/2
    config.certfile = 'cert/cert.pem'  # Path to your SSL certificate
    config.keyfile = 'cert/key.pem'    # Path to your SSL private key
    config.ssl_handshake_timeout = 5

    # Run the server asynchronously with Hypercorn and SSL enabled
    print("Starting Replica Server 1 on https://localhost:8082")
    asyncio.run(serve(app, config))
