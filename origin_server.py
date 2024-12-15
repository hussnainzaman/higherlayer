from flask import Flask, Response, jsonify, send_from_directory
import os
import asyncio
import aiohttp
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Initialize Flask app
app = Flask(__name__)

# Directory where video files are located
VIDEO_DIRECTORY = 'videos'

# List of cache servers (replica servers)
CACHE_SERVERS = [
    'https://localhost:8081', 'https://localhost:8082', 'https://localhost:8083'
]

# ------------------------- Helper Functions -------------------------

def get_video_path(video_name):
    """Constructs the absolute path to a video."""
    return os.path.abspath(os.path.join(VIDEO_DIRECTORY, video_name))

def video_exists_locally(video_name):
    """Checks if a video exists in the local video directory."""
    return os.path.exists(get_video_path(video_name))

async def check_video_on_replicas(video_name):
    """Asynchronously check if the video exists on any replica server."""
    for replica in CACHE_SERVERS:
        try:
            # Disable SSL verification for inter-server requests
            async with aiohttp.ClientSession() as session:
                async with session.head(f"{replica}/{video_name}", ssl=False) as response:
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

    async def replicate_to_server(cache_server):
        try:
            async with aiohttp.ClientSession() as session:
                with open(video_path, 'rb') as video_file:
                    data = aiohttp.FormData()
                    data.add_field('video_name', video_name)
                    data.add_field('video', video_file, filename=video_name, content_type='video/mp4')
                    # Disable SSL verification for inter-server requests
                    async with session.post(f"{cache_server}/replicate", data=data, ssl=False) as response:
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
def home():
    """Welcome endpoint for the server."""
    return "Welcome to the Origin Server!"

@app.route('/videos', methods=['GET'])
def list_videos():
    """Lists all available videos in the video directory."""
    try:
        files = os.listdir(VIDEO_DIRECTORY)
        video_files = [file for file in files if file.lower().endswith('.mp4')]
        return jsonify(video_files), 200, {'Cache-Control': 'max-age=3600, public'}
    except Exception as e:
        print(f"Error reading video directory: {e}")
        return "Error reading video directory", 500

@app.route('/<path:filename>', methods=['GET'])
def serve_video(filename):
    """Serves a video and replicates it to cache servers if not already cached."""
    try:
        # Check if the video exists on replica servers
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        video_cached = loop.run_until_complete(check_video_on_replicas(filename))

        if video_cached:
            print(f"Video {filename} is already cached on replica servers.")
        else:
            # Replicate video to cache servers if not cached
            loop.run_until_complete(replicate_video_to_cache_servers(filename))

        # Serve the video
        response = send_from_directory(VIDEO_DIRECTORY, filename)
        response.headers['Cache-Control'] = 'max-age=3600, public'
        return response
    except Exception as e:
        print(f"Error serving video {filename}: {e}")
        return "Error serving video", 500

# ------------------------- Main Entry Point -------------------------

if __name__ == '__main__':
    # Hypercorn configuration with SSL and HTTP/2 enabled
    config = Config()
    ssl_context = ('cert/cert.pem', 'cert/key.pem')
    config.bind = ["localhost:8080"]
    config.certfile = ssl_context[0]  # Path to SSL certificate
    config.keyfile = ssl_context[1]   # Path to SSL private key
    config.alpn_protocols = ["h2", "http/1.1"]  # Enable HTTP/2 and HTTP/1.1

    print("Starting server on https://localhost:8080 (HTTP/2 enabled)...")

    # Run the Hypercorn server
    asyncio.run(serve(app, config))
