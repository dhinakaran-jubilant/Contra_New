import subprocess
import os
import sys
import time
import socket

# Get absolute paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Define commands
# Use the virtual environment's python.exe for the backend
PYTHON_EXE = os.path.join(BACKEND_DIR, "env", "Scripts", "python.exe")

# Define flags to create new console windows on Windows
CREATE_NEW_CONSOLE = 0x00000010

def get_local_ip():
    try:
        # Create a dummy socket to detect the preferred local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def start_servers():
    print("🚀 Starting Unified Developer Environment...")
    print(f"📂 Base Directory: {BASE_DIR}")
    
    local_ip = get_local_ip()

    # Check for Python Environment
    if not os.path.exists(PYTHON_EXE):
        print(f"❌ Error: Python virtual environment not found at {PYTHON_EXE}")
        print("💡 Please create the environment: cd backend && python -m venv env")
        return

    # Check for Node Modules
    if not os.path.exists(os.path.join(FRONTEND_DIR, "node_modules")):
        print("⚠️ Warning: 'node_modules' not found in frontend.")
        print("💡 Please run: cd frontend && npm install")
        # We continue because they might have fixed it or it might be a false negative
    
    # 1. Sync Database (Create tables automatically if missing)
    print("📂 Syncing Database (makemigrations & migrate)...")
    try:
        subprocess.run([PYTHON_EXE, "manage.py", "makemigrations"], cwd=BACKEND_DIR, check=True)
        subprocess.run([PYTHON_EXE, "manage.py", "migrate"], cwd=BACKEND_DIR, check=True)
        print("✅ Database synced.")
    except Exception as e:
        print(f"⚠️ Database sync encountered issues: {e}")

    # 2. Initialize Admin (Create default admin if not exists)
    print("👤 Initializing Admin User...")
    try:
        subprocess.run([PYTHON_EXE, "manage.py", "init_admin"], cwd=BACKEND_DIR, check=True)
    except Exception as e:
        print(f"⚠️ Admin initialization encountered issues: {e}")

    # 3. Start Backend
    print("⏳ Launching Backend (Django Server on Port 8000)...")
    backend = subprocess.Popen(
        [PYTHON_EXE, "manage.py", "runsslserver", "0.0.0.0:8000"],
        cwd=BACKEND_DIR,
        creationflags=CREATE_NEW_CONSOLE
    )

    # Slight delay to ensure ports don't clash or just for visual clarity
    time.sleep(1)

    # 4. Start Frontend
    print("⏳ Launching Frontend (Vite on Port 3000)...")
    # Using 'cmd /k' keeps the window open so you can see the error if npm fails.
    # shell=True is more reliable for resolving 'npm' on Windows paths.
    frontend = subprocess.Popen(
        "cmd /k npm run dev",
        cwd=FRONTEND_DIR,
        creationflags=CREATE_NEW_CONSOLE,
        shell=True
    )

    print("\n✅ Both servers are starting in NEW windows.")
    print(f"- Backend:  https://localhost:8000 (or https://{local_ip}:8000)")
    print(f"- Frontend: https://localhost:3000 (or https://{local_ip}:3000)")
    print("\nKeep this window open to keep the processes managed, or close it after they start.")
    
    # Keep the script alive so the processes don't orphaned if the user wants management
    print("\nPress Ctrl+C here if you want to exit this manager script.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Manager script exiting. Note: The server windows will remain open.")

if __name__ == "__main__":
    start_servers()
