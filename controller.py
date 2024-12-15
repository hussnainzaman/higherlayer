from quart import Quart, jsonify, Response
import aiohttp
from quart_cors import cors
import asyncio
import ssl

app = Quart(__name__)

# Enable CORS for all origins
app = cors(app, allow_origin="*")

# Define configuration variables for the replica servers
REPLICA_SERVERS = ['https://localhost:8081', 'https://localhost:8082', 'https://localhost:8083']

# Path to the CA certificate
CA_CERT_PATH = 'cert/cert.pem'

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


async def check_video_on_replicas(video_name):
    """Asynchronously check if the video exists on any replica server."""
    ssl_context = ssl.create_default_context(cafile=CA_CERT_PATH)
    for replica in REPLICA_SERVERS:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(f"{replica}/{video_name}", ssl=ssl_context) as response:
                    if response.status == 200:
                        return True  # Video exists on this replica
        except Exception as e:
            print(f"Error checking video on {replica}: {e}")
    return False


async def fetch_video_from_replica(selected_replica, video_name):
    """Fetch the video from the selected replica server."""
    ssl_context = ssl.create_default_context(cafile=CA_CERT_PATH)
    video_url = f"{selected_replica}/{video_name}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url, stream=True, ssl=ssl_context) as response:
                if response.status == 200:
                    async def generate():
                        try:
                            async for chunk in response.content.iter_chunked(1024):
                                yield chunk
                        except Exception as e:
                            print(f"Error during video streaming: {e}")

                    return Response(generate(), content_type='video/mp4')
    except Exception as e:
        print(f"Error fetching video from replica {selected_replica}: {e}")
    return None


@app.route('/')
async def home():
    """Default route to check if the server is running."""
    return "Welcome to the Video Controller!"


@app.route('/<video_name>.mp4')
async def get_video(video_name):
    """Route to handle video streaming requests."""
    video_file = f"{video_name}.mp4"

    # Check if the video is cached on any replica server
    if await check_video_on_replicas(video_file):
        for _ in range(len(REPLICA_SERVERS)):
            selected_replica = get_next_replica(video_name)
            if selected_replica:
                # Fetch the video from the selected replica asynchronously
                video_response = await fetch_video_from_replica(selected_replica, video_file)
                if video_response:
                    return video_response

    # If the video is not cached, fetch it from the origin server
    origin_server_url = f"https://localhost:8080/{video_file}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(origin_server_url, stream=True, ssl=ssl.create_default_context(cafile=CA_CERT_PATH)) as response:
                if response.status == 200:
                    async def generate():
                        try:
                            async for chunk in response.content.iter_chunked(1024):
                                yield chunk
                        except Exception as e:
                            print(f"Error during video streaming: {e}")

                    return Response(generate(), content_type='video/mp4')
    except Exception as e:
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
    config.ssl_handshake_timeout = 50

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
