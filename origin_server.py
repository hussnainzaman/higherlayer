from quart import Quart, Response, jsonify, send_from_directory
import os
import asyncio
import aiohttp
from quart_cors import cors  # Use quart_cors for CORS support
from hypercorn.asyncio import serve
from hypercorn.config import Config
import ssl

# Initialize Quart app
app = Quart(__name__)

# Enable CORS for all routes (allow cross-origin requests)
app = cors(app, allow_origin="*")

# Directory where video files are located
VIDEO_DIRECTORY = 'videos'

# List of cache servers (replica servers)
CACHE_SERVERS = [
    'https://localhost:8081', 'https://localhost:8082', 'https://localhost:8083'
]

# Path to the self-signed CA certificate
CA_CERT_PATH = 'cert/cert.pem'

# ------------------------- Helper Functions -------------------------
def get_ssl_context():
    """Create and return a unified SSL context."""
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile='cert/cert.pem', keyfile='cert/key.pem')
    ssl_context.load_verify_locations(cafile=CA_CERT_PATH)
    ssl_context.verify_mode = ssl.CERT_OPTIONAL
    return ssl_context

def get_ssl_context1():
    """Create and return a unified SSL context."""
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_cert_chain(certfile='cert/cert.pem', keyfile='cert/key.pem')
    ssl_context.load_verify_locations(cafile=CA_CERT_PATH)
    ssl_context.verify_mode = ssl.CERT_OPTIONAL
    return ssl_context

def get_video_path(video_name):
    """Constructs the absolute path to a video."""
    return os.path.abspath(os.path.join(VIDEO_DIRECTORY, video_name))

def video_exists_locally(video_name):
    """Checks if a video exists in the local video directory."""
    return os.path.exists(get_video_path(video_name))

async def check_video_on_replicas(video_name):
    """Asynchronously check if the video exists on any replica server."""
    ssl_context = get_ssl_context() # Use custom CA certificate
    for replica in CACHE_SERVERS:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(f"{replica}/{video_name}", ssl=ssl_context) as response:
                    if response.status == 200:
                        return True  # Video exists on this replica
        except Exception as e:
            print(f"Error checking video on {replica}: {e}")
    return False

async def replicate_video_to_cache_servers(video_name):
    """Asynchronously push the video to all cache servers."""
    video_path = get_video_path(video_name)
    if not video_exists_locally(video_name):
        print(f"Video {video_name} not found locally for replication.")
        return

    print(f"Replicating video {video_name} to all cache servers...")

    ssl_context = get_ssl_context1() # Use custom CA certificate

    async def replicate_to_server(cache_server):
        try:
            async with aiohttp.ClientSession() as session:
                with open(video_path, 'rb') as video_file:
                    data = aiohttp.FormData()
                    data.add_field('video_name', video_name)
                    data.add_field('video', video_file, filename=video_name, content_type='video/mp4')
                    async with session.post(f"{cache_server}/replicate", data=data, ssl=ssl_context) as response:
                        if response.status == 200:
                            print(f"Video {video_name} successfully replicated to {cache_server}")
                        else:
                            print(f"Failed to replicate video {video_name} to {cache_server}: {response.status}")
        except Exception as e:
            print(f"Error replicating video {video_name} to cache server {cache_server}: {e}")

    tasks = [replicate_to_server(server) for server in CACHE_SERVERS]
    await asyncio.gather(*tasks)

# ------------------------- API Endpoints -------------------------

@app.route('/')
async def home():
    """Welcome endpoint for the server."""
    return "Welcome to the Origin Server!"

@app.route('/videos')
async def list_videos():
    """Lists all available videos in the video directory."""
    try:
        files = os.listdir(VIDEO_DIRECTORY)
        video_files = [file for file in files if file.lower().endswith('.mp4')]
        return jsonify(video_files), 200, {'Cache-Control': 'max-age=3600, public'}
    except Exception as e:
        print(f"Error reading video directory: {e}")
        return "Error reading video directory", 500

@app.route('/<path:filename>', methods=['GET'])
async def serve_video(filename):
    """Serves a video or redirects to a replica server if cached."""
    try:
        # Check if the video exists on replica servers
        ssl_context = get_ssl_context1()
        for replica in CACHE_SERVERS:
            try:
                # Check if video is available on the replica server
                async with aiohttp.ClientSession() as session:
                    async with session.head(f"{replica}/{filename}", ssl=ssl_context) as response:
                        if response.status == 200:
                            print(f"Redirecting to cached video on {replica}")
                            return Response(
                                status=302,
                                headers={"Location": f"{replica}/{filename}"}
                            )
            except Exception as e:
                print(f"Error checking video on replica {replica}: {e}")

        # If not cached, replicate video and serve it locally
        print(f"Video {filename} not cached, replicating to cache servers.")
        await replicate_video_to_cache_servers(filename)

        # Serve video locally
        video_path = get_video_path(filename)
        if os.path.exists(video_path):
            return await send_from_directory(VIDEO_DIRECTORY, filename)
        else:
            return jsonify({'error': f'Video {filename} not found'}), 404
    except Exception as e:
        print(f"Error serving video {filename}: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


# ------------------------- Main Entry Point -------------------------

if __name__ == '__main__':
    # Hypercorn configuration with SSL and HTTP/2 enabled
    config = Config()
    config.bind = ["localhost:8080"]
    config.certfile = "cert/cert.pem"  # Path to SSL certificate
    config.keyfile = 'cert/key.pem'   # Path to SSL private key
    config.alpn_protocols = ["h2","http/1.1"]  # Disable HTTP/2 temporarily if needed
    config.shutdown_timeout = 5       # Increase shutdown timeout to avoid errors

    print("Starting server on https://localhost:8080...")

    # Run the Hypercorn server
    asyncio.run(serve(app, config))
