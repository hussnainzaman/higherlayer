from flask import Flask, Response, jsonify, send_from_directory
import os
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Directory where video files are located
video_directory = 'videos'

# List of cache servers (replica servers)
cache_servers = [
    'http://localhost:8081', 'http://localhost:8082', 'http://localhost:8083'
]


def check_video_on_replicas(video_name):
    """Check if the video exists on any replica server."""
    for replica in cache_servers:
        try:
            response = requests.head(f"{replica}/{video_name}")
            if response.status_code == 200:
                return True  # Video exists on this replica
        except requests.exceptions.RequestException as e:
            print(f"Error checking video on {replica}: {e}")
    return False


def replicate_video_to_cache_servers(video_name):
    """Push the video to all cache servers asynchronously."""
    video_path = os.path.abspath(os.path.join(video_directory, video_name))
    if not os.path.exists(video_path):
        print(f"Video {video_name} not found for replication")
        return

    print(f"Replicating video {video_name} to all cache servers...")

    with open(video_path, 'rb') as video_file:
        video_content = video_file.read()

    for cache_server in cache_servers:
        try:
            response = requests.post(
                f"{cache_server}/replicate",
                data={'video_name': video_name},
                files={'video': (video_name, video_content, 'video/mp4')}
            )
            if response.status_code == 200:
                print(f"Video {video_name} successfully replicated to {cache_server}")
            else:
                print(f"Failed to replicate video {video_name} to {cache_server}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error replicating video {video_name} to cache server {cache_server}: {e}")


@app.route('/')
def home():
    return "Welcome to the Origin Server!"


@app.route('/videos', methods=['GET'])
def list_videos():
    try:
        files = os.listdir(video_directory)
        video_files = [file for file in files if file.lower().endswith('.mp4')]
        return jsonify(video_files)
    except Exception as e:
        print(f"Error reading video directory: {e}")
        return "Error reading video directory", 500


@app.route('/<path:filename>', methods=['GET'])
def serve_video(filename):
    # Check if video exists on any cache server
    if check_video_on_replicas(filename):
        print(f"Video {filename} already available on cache servers.")
        return jsonify({'status': 'Video already cached'}), 200

    # Replicate video to cache servers if not cached
    replicate_video_to_cache_servers(filename)

    try:
        video_path = os.path.join(video_directory, filename)
        return send_from_directory(video_directory, filename)
    except Exception as e:
        print(f"Error serving video {filename}: {e}")
        return "Error serving video", 500


if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = ["localhost:8080"]
    # Enable TLS with your certificate and key files
    config.ssl_certfile = "CERT\certificate.pem"
    config.ssl_keyfile = "CERT\private.pem"
    config.alpn_protocols = ["h2"]

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))