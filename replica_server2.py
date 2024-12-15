from flask import Flask, Response, send_file, request
import os

app = Flask(__name__)

# Directory to store replicated videos
replica_video_directory = 'replicated_videos_2'

# Ensure the replica video directory exists
os.makedirs(replica_video_directory, exist_ok=True)

@app.route('/')
def home():
    return "Welcome to Replica Server 2!"

@app.route('/<video_name>', methods=['HEAD', 'GET'])
def serve_replicated_video(video_name):
    # Ensure the video name doesn't include any unwanted paths
    video_name = os.path.basename(video_name)
    video_path = os.path.join(replica_video_directory, f'{video_name}')

    if os.path.exists(video_path):
        if request.method == 'HEAD':
            # For HEAD request, just return 200 if file exists
            return Response(status=200)
        return send_file(video_path, mimetype='video/mp4')

    return 'Video not found', 404

@app.route('/replicate', methods=['POST'])
def replicate_video():
    try:
        # Get video name and content from the request
        video_name = request.form['video_name']
        video_content = request.files['video'].read()

        # Ensure the video name doesn't include any unwanted paths
        video_name = os.path.basename(video_name)

        # Define the path to save the video
        video_path = os.path.join(replica_video_directory, f'{video_name}')

        # Save the replicated video
        with open(video_path, 'wb') as video_file:
            video_file.write(video_content)

        return 'Video replicated successfully', 200
    except Exception as e:
        print(f'Error replicating video: {str(e)}')
        return 'Internal server error', 500

if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = ["localhost:8082"]
    config.alpn_protocols = ["h2"]

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
