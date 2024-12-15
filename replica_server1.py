from flask import Flask, Response, send_file, request
import os

app = Flask(__name__)

# Directory to store replicated videos
REPLICA_VIDEO_DIRECTORY = 'replicated_videos_1'

# Ensure the replica video directory exists
os.makedirs(REPLICA_VIDEO_DIRECTORY, exist_ok=True)

@app.route('/')
def home():
    """
    Welcome endpoint for the replica server.
    """
    return "Welcome to Replica Server 1!"

@app.route('/<video_name>', methods=['HEAD', 'GET'])
def serve_replicated_video(video_name):
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
        # For GET requests, send the video file
        return send_file(video_path, mimetype='video/mp4')

    return Response('Video not found', status=404)

@app.route('/replicate', methods=['POST'])
def replicate_video():
    """
    Replicate a video file to this replica server.

    - Expects the video name and file content in the POST request.
    """
    try:
        # Extract video name and content from the request
        video_name = request.form['video_name']
        video_content = request.files['video'].read()

        # Sanitize the video name to prevent directory traversal
        video_name = os.path.basename(video_name)

        # Define the path to save the video
        video_path = os.path.join(REPLICA_VIDEO_DIRECTORY, video_name)

        # Save the video file to the replica directory
        with open(video_path, 'wb') as video_file:
            video_file.write(video_content)

        return Response('Video replicated successfully', status=200)
    except Exception as e:
        # Log the error for debugging
        print(f'Error replicating video: {str(e)}')
        return Response('Internal server error', status=500)

if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config

    # Configure the server to use HTTP/2
    config = Config()
    config.bind = ["localhost:8081"]  # Set the server to listen on localhost and port 8081
    config.alpn_protocols = ["h2"]    # Enable HTTP/2

    import asyncio
    # Run the server asynchronously with Hypercorn
    asyncio.run(hypercorn.asyncio.serve(app, config))
