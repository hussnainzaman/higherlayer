from flask import Flask, jsonify, Response
import requests

app = Flask(__name__)

# Define configuration variables for the replica servers
REPLICA_SERVERS = ['http://localhost:8081', 'http://localhost:8082', 'http://localhost:8083']

# Initialize round-robin index for each video
round_robin_index = {'video1': 0, 'video2': 0, 'video3': 0}

def get_next_replica(video_name):
    global round_robin_index
    replica_count = len(REPLICA_SERVERS)
    if replica_count == 0:
        return None
    selected_replica = REPLICA_SERVERS[round_robin_index[video_name]]
    round_robin_index[video_name] = (round_robin_index[video_name] + 1) % replica_count
    return selected_replica

def check_video_on_replicas(video_name):
    """Check if the video exists on any replica server."""
    for replica in REPLICA_SERVERS:
        try:
            response = requests.head(f"{replica}/{video_name}")
            if response.status_code == 200:
                return True  # Video exists on this replica
        except requests.exceptions.RequestException as e:
            print(f"Error checking video on {replica}: {e}")
    return False

@app.route('/')
def home():
    return "Welcome to the Video Controller!"

@app.route('/<video_name>.mp4')
def get_video(video_name):
    # Check if the video exists on any replica
    if check_video_on_replicas(f"{video_name}.mp4"):
        for _ in range(len(REPLICA_SERVERS)):
            selected_replica = get_next_replica(video_name)
            if selected_replica:
                try:
                    # Fetch the video from the selected replica server
                    response = requests.get(f"{selected_replica}/{video_name}.mp4", stream=True)
                    if response.status_code == 200:
                        return Response(response.iter_content(chunk_size=1024), content_type='video/mp4')
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching from replica {selected_replica}: {e}")

    # If video is not cached, fetch from origin server
    origin_server_url = f"http://localhost:8080/{video_name}.mp4"
    try:
        response = requests.get(origin_server_url, stream=True)
        if response.status_code == 200:
            return Response(response.iter_content(chunk_size=1024), content_type='video/mp4')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching video from origin server: {e}")

    return jsonify({'error': f'{video_name}.mp4 not available on any server'}), 500

if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = ["localhost:8084"]
    config.alpn_protocols = ["h2"]

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
