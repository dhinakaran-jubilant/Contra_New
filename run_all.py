import subprocess
import os
import sys
import time

# Get absolute paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Define commands
# Use the virtual environment's python.exe for the backend
PYTHON_EXE = os.path.join(BACKEND_DIR, "env", "Scripts", "python.exe")

# Define flags to create new console windows on Windows
CREATE_NEW_CONSOLE = 0x00000010

def start_servers():
    print("🚀 Starting Unified Developer Environment...")
    print(f"📂 Base Directory: {BASE_DIR}")
    
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

    # Start Frontend
    print("⏳ Launching Frontend (Vite on Port 3000)...")
    frontend = subprocess.Popen(
        ["cmd", "/c", "npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        creationflags=CREATE_NEW_CONSOLE
    )

    print("\n✅ Both servers are starting in NEW windows.")
    print("- Backend: https://localhost:8000")
    print("- Frontend: https://localhost:3000 (or https://192.168.0.7:3000)")
    print("\nKeep this window open to keep the processes managed, or close it after they start.")
    
    # Keep the script alive so the processes don't orphaned if the user wants management
    # But usually, with CREATE_NEW_CONSOLE, they are independent windows.
    print("\nPress Ctrl+C here if you want to exit this manager script.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Manager script exiting. Note: The server windows will remain open.")

if __name__ == "__main__":
    start_servers()
