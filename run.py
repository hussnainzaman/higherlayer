import subprocess

python_files = [
    'app.py',
    'origin_server.py',
    'controller.py',
    'replica_server1.py',
    'replica_server2.py',
    'replica_server3.py'
]

processes = []

for file in python_files:
    process = subprocess.Popen(
        ['python', file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes.append((file, process))

# Monitor for errors in real-time
for file, process in processes:
    stdout, stderr = process.communicate()
    print(f"Output from {file}:")
    print(stdout)
    print(f"Errors from {file}:")
    print(stderr)

print("All scripts executed.")
