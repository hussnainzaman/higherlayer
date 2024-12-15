import subprocess

# List of Python files you want to run
python_files = [
    'app.py',
    'origin_server.py',
    'controller.py',
    'replica_server1.py',
    'replica_server2.py',
    'replica_server3.py'
]


# List to hold the processes
processes = []

# Loop through the list and start each script as a subprocess
for file in python_files:
    process = subprocess.Popen(['python', file])
    processes.append(process)

# Wait for all processes to finish
for process in processes:
    process.wait()

print("All scripts executed.")
