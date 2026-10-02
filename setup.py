import subprocess
import sys
import os

# Define required system and python packages
system_packages = ["tmux", "xfce4-terminal", "xclip"]
python_packages = ["google-generativeai", "python-dotenv"]


#========================================================================
# Colors
# just setting up some colours for making the output look nicer.
red = "\033[91m"; green = "\033[32m"; blue = "\033[94m"; purple = "\033[95m"
gold = "\033[38;5;220m"; cyan = "\033[36m"; yellow = "\033[93m"; reset = "\033[0m"
#========================================================================


# Scripts to make executable
scripts_to_make_executable = ["ai-terminal-x.py", "command_suggester.py", "run.sh"]

def install_system_packages():
    print(f"{gold}>>> Installing required system packages...{reset}")
    try:
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y"] + system_packages, check=True)
        print(f"{gold}>>> System packages installed successfully.{reset}")
    except subprocess.CalledProcessError:
        print(f"{red} Failed to install system packages. Make sure you're using a Debian-based system with sudo access.")

def setup_virtualenv():
    print(f"{blue} Setting up Python virtual environment...{reset}")
    if not os.path.exists("venv"):
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print(f"{gold}>>> Virtual environment created.{reset}")
    else:
        print(f"{gold}>>> Virtual environment already exists{reset}")

def install_python_packages():
    print(f"{gold} Installing Python packages inside virtual environment...{reset}")
    try:
        subprocess.run(["venv/bin/python", "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run(["venv/bin/python", "-m", "pip", "install"] + python_packages, check=True)
        print(f"{gold} Python packages installed successfully.{reset}")
    except subprocess.CalledProcessError:
        print(f"{red} Failed to install Python packages{reset}")

def create_run_script():
    print(f">>>>{gold} Creating run.sh to auto-activate venv and launch the tool...{reset}")
    script_content = """#!/bin/bash
# Activate virtual environment and run the main script
if [ ! -f venv/bin/activate ]; then
    echo "Virtual environment not found. Run 'python setup.py' first."
    exit 1
fi
source venv/bin/activate
echo "Starting the Powerful Ai-Based Linux Terminal....."
python ai-terminal-x.py
"""
    with open("run.sh", "w") as f:
        f.write(script_content)
    print(f">>> {green} run.sh created.")

def make_scripts_executable():
    print(f"{blue} Setting executable permissions...{reset}")
    for script in scripts_to_make_executable:
        if os.path.exists(script):
            try:
                subprocess.run(["chmod", "+x", script], check=True)
                print(f">>> {gold}{script} is now executable.")
            except subprocess.CalledProcessError:
                print(f">>>{red} Failed to set permission for {script}.")
        else:
            print(f"{red}>>>>  Script not found: {script}")

def print_final_message():
    print(f"\n✔{gold} Setup completed successfully!")
    print(">>>> You can now run the tool using:\n")
    print(f">>> {gold}./run.sh {reset} or >>> {gold} bash run.sh\n")
    print(f">>>> {green} Make sure you're in the correct directory.\n")

def main():
    print(f">>> {green} Starting setup for ai-terminal-x...")
    install_system_packages()
    setup_virtualenv()
    install_python_packages()
    create_run_script()
    make_scripts_executable()
    print_final_message()

if __name__ == "__main__":
    main()
