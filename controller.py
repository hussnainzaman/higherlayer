from flask import Flask, jsonify, Response
import requests
from flask_cors import CORS 
app = Flask(__name__)

CORS(app, origins="*", methods=["GET", "POST"], supports_credentials=True)


# Define configuration variables for the replica servers
REPLICA_SERVERS = ['https://localhost:8081', 'https://localhost:8082', 'https://localhost:8083']

# Initialize round-robin index for each video (ensures even distribution of requests)
round_robin_index = {}

def get_next_replica(video_name):
    """Retrieve the next replica server for the given video using round-robin logic."""
    global round_robin_index
    if video_name not in round_robin_index:
        round_robin_index[video_name] = 0  # Initialize index if not present

    replica_count = len(REPLICA_SERVERS)
    if replica_count == 0:
        return None

    # Select the replica based on the current index
    selected_replica = REPLICA_SERVERS[round_robin_index[video_name]]
    round_robin_index[video_name] = (round_robin_index[video_name] + 1) % replica_count  # Increment index
    return selected_replica

def check_video_on_replicas(video_name):
    """Check if the video exists on any replica server by sending HEAD requests."""
    for replica in REPLICA_SERVERS:
        try:
            # Disable SSL verification only for inter-server requests
            response = requests.head(f"{replica}/{video_name}", verify=False)
            if response.status_code == 200:
                return True  # Video exists on this replica
        except requests.exceptions.RequestException as e:
            print(f"Error checking video on {replica}: {e}")
    return False

@app.route('/')
def home():
    """Default route to check if the server is running."""
    return "Welcome to the Video Controller!"

@app.route('/<video_name>.mp4')
def get_video(video_name):
    """Route to handle video streaming requests."""
    video_file = f"{video_name}.mp4"

    # Check if the video is cached on any replica server
    if check_video_on_replicas(video_file):
        for _ in range(len(REPLICA_SERVERS)):
            selected_replica = get_next_replica(video_name)
            if selected_replica:
                try:
                    # Fetch the video from the selected replica server
                    response = requests.get(f"{selected_replica}/{video_file}", stream=True, verify=False)
                    if response.status_code == 200:
                        def generate():
                            try:
                                for chunk in response.iter_content(chunk_size=1024):
                                    if chunk:
                                        yield chunk
                            except GeneratorExit:
                                print("Streaming stopped by client.")
                            except Exception as e:
                                print(f"Error during video streaming: {e}")

                        return Response(generate(), content_type='video/mp4')
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching from replica {selected_replica}: {e}")

    # If the video is not cached, fetch it from the origin server
    origin_server_url = f"https://localhost:8080/{video_file}"
    try:
        response = requests.get(origin_server_url, stream=True, verify=True)  # Verify SSL for origin server
        if response.status_code == 200:
            def generate():
                try:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            yield chunk
                except GeneratorExit:
                    print("Streaming stopped by client.")
                except Exception as e:
                    print(f"Error during video streaming: {e}")

            return Response(generate(), content_type='video/mp4')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching video from origin server: {e}")

    # If the video is not available on any server, return an error response
    return jsonify({'error': f'{video_file} not available on any server'}), 500

if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config

    # Configure the Hypercorn server for HTTP/2
    config = Config()
    config.bind = ["localhost:8084"]  # Bind the server to localhost on port 8084
    config.alpn_protocols = ["h2", "http/1.1"]  # Enable HTTP/2
    config.certfile = "cert/cert.pem"  # Specify the SSL certificate
    config.keyfile = "cert/key.pem"  # Specify the SSL key
    config.ssl_handshake_timeout = 5

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
