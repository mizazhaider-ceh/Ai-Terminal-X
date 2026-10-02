#!/usr/bin/env python3 
# -*- coding: utf-8 -*-

# Ai-Terminal-X: Your AI-Powered Linux Assistant 
# After launching the Ai-Terminal-X i thought i should make one for linux ...it have more power then that ai-terminal-x

# --- Required libraries ---
# pip install google-generativeai python-dotenv
# Tools: tmux xfce4-terminal xclip 
# --------------------------

# bringing in the google ai stuff.
import google.generativeai as genai
# needed for working with file paths and environment variables.
import os
# helps load secrets from a .env file.
from dotenv import load_dotenv
# this is key for running other programs like tmux or the command suggester.
import subprocess # IMPORTANT: Used to run external programs AND the suggester script
# for timestamping the logs.
import datetime
# used to find the python interpreter and exit the script cleanly.
import sys # Needed for sys.executable and sys.exit
# helps find external tools like tmux.
import shutil
# used for pausing briefly, like when waiting for tmux.
import time


#========================================================================
# Colors
# just setting up some colours for making the output look nicer.
red = "\033[91m"; green = "\033[32m"; blue = "\033[94m"; purple = "\033[95m"
gold = "\033[38;5;220m"; cyan = "\033[36m"; yellow = "\033[93m"; reset = "\033[0m"
#========================================================================

# --- Configuration ---
# settings for how the script behaves.
# the name we'll give our special tmux window.
TMUX_VIEWER_SESSION_NAME = "ai-terminal-x-interactive-viewer"
# which terminal program to pop open for visual output. make sure it likes the -e flag.
VISUAL_TERMINAL = "xfce4-terminal" # Make sure this terminal supports the -e flag correctly
# how much scrollback history to keep in the tmux viewer.
TMUX_HISTORY_LIMIT = 30000
# the file where we expect to find the gemini api key.
API_KEY_FILENAME = ".env"
# the gemini model used for command generation and risk checks.
AI_MODEL_NAME = "gemini-2.0-flash"
# --- NEW/MODIFIED ---
# the name of the helper script that gives command suggestions.
COMMAND_SUGGESTER_SCRIPT = "command_suggester.py" # Name of the helper script

# --- Global variables ---
# these variables hold info that needs to be accessible across different functions.
# we'll store the full paths to these tools once we find them.
tmux_path_global = None
visual_term_path_global = None
xclip_path_global = None
# a flag to keep track if the tmux viewer window is currently running.
persistent_viewer_active = False

# --- Function to Load API Key ---
# (Keep the existing load_api_key function as it was)
# this function tries to get the api key needed for google's ai.
def load_api_key():
    """Loads Gemini API Key from .env or prompts user."""
    # Construct the full path to the .env file relative to this script's location
    # figure out where this script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # build the full path to the .env file we're looking for.
    dotenv_path = os.path.join(script_dir, API_KEY_FILENAME)

    # check if the .env file actually exists.
    if os.path.exists(dotenv_path):
        print(f"{blue}Found '{API_KEY_FILENAME}' at '{dotenv_path}'. Reading key...{reset}")
        # load the variables from the .env file.
        load_dotenv(dotenv_path=dotenv_path)
        # try to get the specific api key variable.
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            # success. we found the key.
            print(f"{green}API Key loaded successfully.{reset}")
            return api_key
        else:
            # the file exists but the key variable is missing inside it.
            print(f"{red}Key 'GEMINI_API_KEY' missing in '{dotenv_path}'.{reset}")
    else:
        # the .env file wasn't found where we expected it.
        print(f"{blue}No '{API_KEY_FILENAME}' file found at '{dotenv_path}'.{reset}")

    # if we got here, we need to ask the user for the key.
    print(f"{yellow}Please enter your Gemini API Key (will be saved to '{dotenv_path}'):{reset}")
    api_key = input(f"{green}Paste key here: {reset}").strip()
    # if they didn't enter anything, we can't continue.
    if not api_key:
        print(f"{red}No API key entered. Exiting.{reset}")
        sys.exit(1)
    # try to save the key they entered into the .env file.
    try:
        with open(dotenv_path, "w") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")
        print(f"{gold}API key saved to '{dotenv_path}'.{reset}")
        # also set it as an environment variable for this current script run.
        os.environ["GEMINI_API_KEY"] = api_key
    except Exception as e:
        # something went wrong trying to save the file.
        print(f"{red}Error saving API key to '{dotenv_path}': {e}.{reset}")
        # maybe it was already set some other way? let's try to use the entered key anyway.
        api_key = os.getenv("GEMINI_API_KEY", api_key) # Use entered key if save failed but env var might exist

    # final check, if we still don't have a key after trying to save/load, give up.
    if not api_key: # Check again if saving failed and it wasn't set otherwise
         print(f"{red}Could not obtain API key. Exiting.{reset}")
         sys.exit(1)
    # return the key we managed to get.
    return api_key


# --- Function to Setup Google AI ---
# (Keep the existing configure_ai function as it was)
# sets up the connection to the google ai using the api key.
def configure_ai(api_key):
    """Configures Google AI. Returns model object or exits."""
    try:
        print(f"{blue}Configuring Google AI connection...{reset}")
        # tell the google ai library about our key.
        genai.configure(api_key=api_key)
        # choose the specific ai model we want to use (flash is good for speed/cost).
        model = genai.GenerativeModel(AI_MODEL_NAME)
        print(f"{green}Google AI configured successfully!{reset}"); return model
    except Exception as e:
        # uh oh, something went wrong during setup.
        print(f"{red}\n--- FATAL AI CONFIGURATION ERROR ---{reset}")
        print(f"{red}Error details: {e}{reset}")
        # try to give more specific advice based on the error message.
        if "api key not valid" in str(e).lower():
             print(f"{red}Your Gemini API Key appears INVALID. Please check or replace '{API_KEY_FILENAME}'.{reset}")
             # if the key is bad, maybe try deleting the .env file so the user is prompted again next time.
             script_dir = os.path.dirname(os.path.abspath(__file__))
             dotenv_path = os.path.join(script_dir, API_KEY_FILENAME)
             if os.path.exists(dotenv_path):
                 try:
                     os.remove(dotenv_path)
                     print(f"{yellow}Removed the potentially invalid '{API_KEY_FILENAME}'. Please restart the script to enter a new key.{reset}")
                 except Exception as rm_err:
                     print(f"{yellow}Could not remove '{API_KEY_FILENAME}': {rm_err}{reset}")
        elif "quota" in str(e).lower():
            # maybe they used the api too much.
            print(f"{yellow}You might have exceeded your API usage quota. Check your Google AI Studio/Cloud console.{reset}")
        elif "permission" in str(e).lower():
            # the key might be valid but lack permissions.
            print(f"{yellow}Permission denied. Ensure the API key is enabled and has permissions for the Generative Language API.{reset}")
        else:
            # some other generic error.
            print(f"{yellow}This could be a network issue, an API outage, or another configuration problem.{reset}")
        # can't proceed without a working ai connection.
        print(f"{red}Cannot continue without a valid AI configuration. Exiting.{reset}")
        sys.exit(1)


# --- Define AI Prompts ---
# these are the instructions we give to the ai.
# the main set of rules for asking the ai to generate a linux command and explanation.
base_prompt = """
You are an AI assistant that generates accurate Linux Bash commands based on user requests.
The input request may be written in any language (such as English, Urdu, Hindi, Arabic, Spanish, etc.),
and you must intelligently understand and interpret the task regardless of the language used.
Your job is to output only the Bash command and a one-line explanation.
The first line of your response should be the correct and commonly used Linux Bash command using standard tools.
The second line should begin with “Explanation:” followed by a concise sentence that clearly describes the command’s main function and any key options used.
You must avoid any extra text, greetings, or markdown — just the command and explanation in plain text.

Keep the command simple and correct by default, unless the user specifically requests a complex operation. If complexity is required, ensure that the use of pipes or logical operators still fits neatly on a single command line. Regardless of the input language, always detect the intent properly and respond as if the request were made in English. The explanation must always remain in English only for consistency, even if the request is in another language.

Example Request in English:
list files with details
Response:
ls -lah
Explanation: Lists all files (including hidden) in long format with human-readable sizes.

Example Request in Urdu:
تمام فائلیں تفصیل کے ساتھ دکھائیں
Response:
ls -lah
Explanation: Lists all files (including hidden) in long format with human-readable sizes.

The task is : {INPUT}

"""
# the instructions for asking the ai if a command looks dangerous.
risk_check_prompt = """
Analyze risk of Linux command: `{COMMAND}`
Is it potentially destructive (data loss/modification, system config change, format) OR does it typically require sudo/root privileges to run safely/effectively?
- If YES: Respond with "Risky: [Brief one-sentence explanation of the primary risk]". Example: "Risky: Force deletes files/directories recursively without confirmation." Example: "Risky: Modifies system network configuration and usually requires sudo." Example: "Risky: Formats a disk partition, causing complete data loss."
- If NO: Respond with exactly "Safe".
ONLY output the result ("Risky: ..." or "Safe"). No extra text. Assume the user might run it in any directory without necessarily knowing the full implications.
"""


# --- Functions for AI Interaction ---
# (Keep the existing validate_command_risk, gemini_command_and_explanation, explain_command functions)
# asks the ai if a given command might be risky to run.
def validate_command_risk(model, command_to_check):
    """Asks AI if command is risky. Handles safety blocks."""
    # don't bother if the command is empty.
    if not command_to_check: return None
    # put the actual command into our risk check prompt template.
    prompt = risk_check_prompt.replace("{COMMAND}", command_to_check)
    print(f"{cyan}~~ Strictly Asking AI for risk check (Don't worry)...{reset}")
    try:
        # use stricter safety settings for this check, we don't want the *check itself* generating something bad.
        # but allow checking potentially dangerous content so the ai can assess it.
        safety_settings_risk = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"} # Block obviously dangerous generation here too
        ]
        # send the prompt to the ai.
        response = model.generate_content(prompt, safety_settings=safety_settings_risk) 
        # figure out why the ai finished (or didn't).
        finish_reason = None
        block_reason_detail = "Unknown"
        try: # Safely access response details
             # check if the response got blocked by the safety filter.
             if response.candidates:
                 candidate = response.candidates[0]
                 finish_reason = getattr(candidate, 'finish_reason', 'Unknown')
                 if finish_reason == 3: # 3 = Safety
                    block_reason_detail = "Safety Filter"
                    # try to find out which specific safety category caused the block.
                    if hasattr(candidate, 'safety_ratings'):
                        blocked_ratings = [f"{r.category.name}={r.probability.name}" for r in candidate.safety_ratings if getattr(r,'blocked', False)]
                        if blocked_ratings: block_reason_detail = ", ".join(blocked_ratings)
        except Exception: pass # Ignore errors checking safety details
        # if it was blocked by safety, we can't trust the command.
        if finish_reason == 3:
            print(f"{yellow}  Warn: AI Safety BLOCKED the risk assessment itself ({block_reason_detail}).{reset}")
            return "AI safety filter blocked assessment; treat command as potentially risky."
        # get the text part of the ai's response.
        response_text = getattr(response, 'text', None)
        # if the response was empty (and not blocked), that's weird. assume risky.
        if not response_text or not response_text.strip():
            print(f"{yellow}  Warn: No text in risk assessment response (Reason: {finish_reason}).{reset}")
            # return None # Treat as safe if no text and not blocked? Or risky? Let's say risky.
            return "AI gave empty response for risk; treat command as potentially risky."

        response_text = response_text.strip()
        # check if the response starts with "risky:".
        if response_text.startswith("Risky:"):
            print(f"{green}>>> AI assessment: {red}Risky{reset}")
            # return just the explanation part after "risky:".
            return response_text[len("Risky:"):].strip()
        # check if the response is exactly "safe".
        elif response_text == "Safe":
            print(f"\n{gold}>>>  AI assessment: {blue} Safe{reset}")
            # return nothing (none) for safe commands.
            return None # Return None for Safe
        else:
            # the ai didn't respond in the format we expected. treat as risky just in case.
            print(f"{yellow}  Warn: Unexpected risk response format: '{response_text}'. Treating as potentially risky.{reset}")
            return f"Unexpected AI response format ('{response_text}'); treat command as potentially risky."
    except Exception as e:
        # an error happened during the api call itself. treat as risky.
        print(f"{red}  Error during risk check API call: {e}{reset}")
        return "Risk assessment failed due to API error; treat command as potentially risky."

# this talks to the ai to get the actual command and its explanation based on what the user asked for.
def gemini_command_and_explanation(model, user_input):
    """Gets command/explanation from AI for Quick/Interactive modes."""
    # ignore empty requests.
    if not user_input.strip(): return None, None, f"{red}Input request is empty.{reset}"
    # fill in the user's request into the main prompt template.
    prompt = base_prompt.replace("{INPUT}", user_input)
    print(f"{gold}\n>>>>{blue} Asking AI for command for request: '{user_input}'...{reset}")
    try:
        # use standard safety settings here, block medium and above harmful content.
        safety_settings_cmd = [
            {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
        ]
        # send the request to the ai.
        response = model.generate_content(prompt, safety_settings=safety_settings_cmd)
        print(f"{gold}>>>> Wow,{blue} AI has responded.{reset}")
        finish_reason = None; block_reason_detail = "Unknown"
        try: # Check for blocks
             # check if the response was blocked by safety filters.
             if response.candidates:
                 candidate = response.candidates[0]
                 finish_reason = getattr(candidate, 'finish_reason', 'Unknown')
                 if finish_reason == 3: # Safety block
                     block_reason_detail = "Safety Filter"
                     if hasattr(candidate, 'safety_ratings'):
                         blocked_ratings = [f"{r.category.name}={r.probability.name}" for r in candidate.safety_ratings if getattr(r,'blocked', False)]
                         if blocked_ratings: block_reason_detail = ", ".join(blocked_ratings)
        except Exception: pass
        # if blocked, return an error message.
        if finish_reason == 3:
            return None, None, f"{red}AI request blocked by safety filter (Reason: {block_reason_detail}). Try rephrasing.{reset}"

        # get the text from the response.
        response_text = getattr(response, 'text', None)
        # if response is empty, return an error.
        if not response_text or not response_text.strip():
            return None, None, f"{red}AI response was empty (Finish Reason: {finish_reason}).{reset}"

        # split the response into lines (expecting command on first, explanation on second).
        lines = response_text.strip().split('\n', 1)
        # get the first line as the command.
        command = lines[0].strip()
        explanation = ""
        # if the command line is empty, that's an error.
        if not command:
            return None, None, f"{red}AI response did not contain a command on the first line.{reset}\nRaw Response:\n{response_text}{reset}"
        # carefully check if the second line starts with "explanation:".
        if len(lines) > 1 and lines[1].strip().startswith("Explanation:"):
            # extract the explanation text.
            explanation = lines[1].replace("Explanation:", "", 1).strip()
        elif len(lines) > 1:
             # the second line exists but doesn't look like our expected explanation format. warn the user.
             print(f"{yellow}Warning: Second line from AI did not start with 'Explanation:'. Treating as part of command or ignoring.{reset}")
             # Decide: treat as explanation or ignore? Let's ignore for now to keep command clean.
             # explanation = lines[1].strip() # Option to keep it anyway

        # return the command, explanation, and no error message (none).
        return command, explanation, None # Success
    except Exception as e:
        # handle errors during the api communication.
        print(f"{red}Error communicating with AI: {e}{reset}")
        return None, None, f"{red}Failed to get command due to API communication error.{reset}"

# asks the ai to explain a specific command or topic the user typed in.
def explain_command(model, command_input):
    """Asks AI to explain a concept or command."""
    # use a slightly different prompt for explanations.
    prompt = f"""
    "Imagine you're explaining the following Linux concept or command "
    "to someone who’s new to Linux. Make the explanation clear, concise, "
    "and easy to understand. Focus on the main purpose, common usage, "
    "and why someone would use this command in real-world scenarios. "
    "If the command is part of the explanation, include it clearly with a brief example. "
    "Format the output as follows:\n\n"

    "Imagine this: (2-3 lines describing the context or scenario where the command would be used)\n"
    "Explanation: (2-3 lines explaining the command’s main purpose, how it works, and why it's useful)\n"
    "Command: (The actual Linux command for clarity)\n"
    "Example: (A practical example to show how the command is used with output or a scenario)"

    "Here is the concept or command I want to explain:\n\n"
    "{command_input}\n\n"
    """
    
    print(f"~~~{blue} Asking AI for explanation of '{command_input[:50]}...'...{reset}")
    try:
        # use slightly less strict safety for explanations, but still block obviously bad stuff.
        safety_settings_explain = [
            {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
        ]
        # send the explanation request to the ai.
        response = model.generate_content(prompt, safety_settings=safety_settings_explain)

        finish_reason = "Unknown"; block_reason_detail = "Unknown"
        try:
             # check if the explanation request was blocked.
             if response.candidates:
                 candidate = response.candidates[0]; finish_reason = getattr(candidate,'finish_reason', 'Unknown')
                 if finish_reason == 3: # Blocked
                    block_reason_detail = "Safety Filter"
                    if hasattr(candidate, 'safety_ratings'):
                         blocked_ratings = [f"{r.category.name}={r.probability.name}" for r in candidate.safety_ratings if getattr(r,'blocked', False)]
                         if blocked_ratings: block_reason_detail = ", ".join(blocked_ratings)
        except Exception: pass

        # if blocked, return an error message.
        if finish_reason == 3:
             return f"{red}AI explanation request blocked (Reason: {block_reason_detail}).{reset}"

        # get the explanation text from the response.
        response_text = getattr(response, 'text', None)
        if response_text and response_text.strip():
            # success, return the explanation.
            return response_text.strip() # Return the explanation text
        else:
             # the ai gave an empty response.
             return f"{red}Couldn't get explanation (AI gave empty response, reason: {finish_reason}).{reset}"
    except Exception as e:
        # handle api errors during explanation request.
        print(f"{red}Explain command API error: {e}{reset}")
        return f"{red}Error occurred while trying to get explanation.{reset}"


# --- Function to detect explanation requests ---
# checks whether the user's input is asking for an explanation
# (e.g. "explain grep", "what is ssh"). returns a tuple:
# (triggered, topic, matched_prefix). topic is None when the user
# typed a prefix with nothing after it. kept separate so it is testable.
def detect_explain_request(user_input):
    """Detects 'explain <topic>' style requests. Returns (triggered, topic, prefix)."""
    explain_prefixes = ("explain ", "what is ", "what's ", "tell me about ", "describe ")
    user_input_lower = user_input.lower()
    for prefix in explain_prefixes:
        if user_input_lower.startswith(prefix):
            # make sure there's something *after* the prefix.
            if len(user_input) > len(prefix):
                # extract the topic they want explained.
                return True, user_input[len(prefix):].strip(), prefix
            # they typed the prefix but nothing else.
            return True, None, prefix
    return False, None, None


# --- Check for Required External Tools ---
# (Keep the existing check_external_tools function)
# makes sure the necessary command-line tools (tmux, terminal, xclip) are installed and findable.
def check_external_tools():
    """Finds paths & exits if mandatory missing."""
    global tmux_path_global, visual_term_path_global, xclip_path_global
    print(f"{blue}Checking required tools...{reset}")
    # use shutil.which to find the full path to each tool.
    tmux_path_global = shutil.which('tmux')
    visual_term_path_global = shutil.which(VISUAL_TERMINAL)
    xclip_path_global = shutil.which('xclip') # Optional

    missing = []
    # tmux and the visual terminal are considered mandatory.
    if not tmux_path_global:
        missing.append("'tmux'")
    if not visual_term_path_global:
        missing.append(f"'{VISUAL_TERMINAL}' (or configure a different VISUAL_TERMINAL)")

    # if any mandatory tools are missing, print an error and exit.
    if missing:
        print(f"{red}Error: Cannot find required command(s): {', '.join(missing)}.{reset}")
        print(f"{yellow}Please Run {gold} python setup.py{reset} then run {gold}bash run.sh{reset}")
        sys.exit(1)

    # report the tools that were found.
    print(f"{green}Found: tmux, {VISUAL_TERMINAL}{reset}")
    if xclip_path_global:
        # xclip is optional, used for copying to clipboard.
        print(f"{green}Found: xclip (optional, for copy-to-clipboard){reset}")
    else:
        print(f"{yellow}Optional 'xclip' not found. Copy-to-clipboard feature disabled.{reset}")


# --- Function to select execution mode ---
# (Keep the existing select_execution_mode function)
# asks the user whether they want commands to run in one continuous window or a new one each time.
def select_execution_mode():
    """Asks user: Persistent (single viewer) or Separate (new window each time)."""
    global persistent_viewer_active
    # reset the flag that tracks if the persistent viewer is active.
    persistent_viewer_active = False # Reset flag each time mode is selected
    # keep asking until they choose 1 or 2.
    while True:
        
        print(f"\n>>>> Select Execution Style for Commands <<<<\n")
        print(f"{gold}[1] Persistent Viewer{reset}{blue}\t(ONE '{VISUAL_TERMINAL}' window shows all command outputs. Good for sequences.){reset}")
        print(f"{gold}[2] Separate Window{reset}{blue}\t(NEW '{VISUAL_TERMINAL}' window with pause for each command. Good for isolated tasks.){reset}")
        choice = input(f"\n>>>{green} Enter choice (1 or 2): {reset}").strip()
        # handle choice 1 (persistent).
        if choice == "1":
            banner1 = f"""{gold}
                ───▄▀▀▀▄▄▄▄▄▄▄▀▀▀▄───  OMG...NiCe ChoIce....
                ───█▒▒░░░░░░░░░▒▒█─── 
                ────█░░█░░░░░█░░█────  "Stay Consistant to learning"
                ─▄▄──█░░░▀█▀░░░█──▄▄─
                █░░█─▀▄░░░░░░░▄▀─█░░█{reset}
            """
            print(f"\n{banner1}")
            print(f"\t~ Persistent Viewer mode selected.")
            # return the string identifying this mode.
            return "persistent_single_viewer"
        # handle choice 2 (separate).
        elif choice == "2":
            banner2 = f"""{gold}
                ░░▄▄░▄███▄      (Let's Click A Picture of You...)
                ▄▀▀▀▀░▄▄▄░▀▀▀▀▄ 
                █▒▒▒▒█░░░█▒▒▒▒█    OMG....You Are so Nice Person...
                █▒▒▒▒▀▄▄▄▀▒▒▒▒█ 
                ▀▄▄▄▄▄▄▄▄▄▄▄▄▄▀{reset}
            """
            print(f"\n{banner2}")
            print(f"\t~ Separate Window mode selected.")
            # return the string identifying this mode.
            return "separate_pause_window"
        else:
            # they entered something other than 1 or 2. ask again.
            print(f"{red}Invalid choice. Please enter 1 or 2.{reset}")


# --- Tmux/Terminal Helper Functions ---
# (Keep the existing check_tmux_session, send_command_to_tmux_viewer, send_interrupt_to_tmux_viewer, launch_persistent_viewer_if_needed, run_visual_pause_window functions)
# checks if a tmux session with the given name is already running.
def check_tmux_session(session_name):
    """Checks if tmux session exists using 'tmux has-session'."""
    # if tmux wasn't found earlier, we can't check.
    if not tmux_path_global: return False # Should not happen if check_external_tools passed
    try:
        # run 'tmux has-session -t <session_name>' command.
        # use a timeout in case the tmux server is stuck.
        proc = subprocess.run([tmux_path_global,'has-session','-t', session_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        # if the command returns 0, the session exists.
        return proc.returncode == 0 # 0 means session exists
    except subprocess.TimeoutExpired:
        # the check timed out. assume it doesn't exist.
        print(f"{yellow}Warn: Timeout checking tmux session '{session_name}'. Assuming it doesn't exist.{reset}")
        return False
    except Exception as e:
        # some other error occurred during the check. assume it doesn't exist.
        print(f"{yellow}Warn: Error checking tmux session '{session_name}': {e}. Assuming it doesn't exist.{reset}")
        return False

# sends the generated command (plus an 'enter' key press) to the running tmux viewer window.
def send_command_to_tmux_viewer(session_name, command):
    """Sends command string + Enter to tmux pane. Resets flag on failure."""
    global persistent_viewer_active
    # can't send if tmux isn't available.
    if not tmux_path_global: return False
    # target the first pane (0.0) in the first window (0) of the session.
    target_pane = f"{session_name}:0.0" # Target the first window, first pane
    try:
        # send-keys takes the command as a plain argument, so no shell
        # quoting is needed here. tmux types it into the pane for us.
        # use 'tmux send-keys' to type the command into the target pane, followed by 'c-m' (ctrl+m, which is enter).
        send_args = [tmux_path_global, 'send-keys', '-t', target_pane, command, 'C-m'] # C-m is Enter

        # run the tmux command, check for errors, capture output (though we don't use it here), set a timeout.
        subprocess.run(send_args, check=True, capture_output=True, text=True, timeout=5)
        # if it didn't raise an error, it worked.
        return True
    except subprocess.TimeoutExpired:
        # sending the command timed out. assume the viewer is broken.
        print(f"{red}Error: Timeout sending command to tmux '{target_pane}'.{reset}")
        # set the flag to false since the viewer seems unresponsive.
        persistent_viewer_active = False # Assume viewer is unresponsive
        return False
    except subprocess.CalledProcessError as e:
        # the tmux command failed. check the error message.
        stderr_lower = e.stderr.strip().lower() if e.stderr else ""
        # common errors mean the session or pane is gone.
        if "no server running" in stderr_lower or "session not found" in stderr_lower or "pane not found" in stderr_lower:
            print(f"{yellow}Warn: Target tmux pane '{target_pane}' not found. Viewer likely closed.{reset}")
        else:
             # some other tmux error occurred.
             print(f"{red}Error sending command to tmux '{target_pane}': {e.stderr.strip()}{reset}")
        # if sending failed, assume the viewer is gone.
        persistent_viewer_active = False # Assume viewer is gone if send fails
        return False
    except Exception as e:
        # an unexpected python error happened.
        print(f"{red}Unexpected error sending command to tmux '{target_pane}': {e}{reset}")
        persistent_viewer_active = False
        return False

# sends a ctrl+c signal to the tmux viewer to try and stop the running command.
def send_interrupt_to_tmux_viewer(session_name):
    """Sends Ctrl+C (SIGINT) to the tmux viewer session's first pane."""
    global persistent_viewer_active
    # need tmux to send the signal.
    if not tmux_path_global: return False
    # target the same pane as before.
    target_pane = f"{session_name}:0.0"
    print(f"{blue}~ Sending interrupt (Ctrl+C) signal to {target_pane}...{reset}")
    try:
        # use 'tmux send-keys' with 'c-c' to simulate pressing ctrl+c in the pane.
        interrupt_args = [tmux_path_global, 'send-keys', '-t', target_pane, 'C-c']
        # run the command with a short timeout.
        subprocess.run(interrupt_args, check=True, capture_output=True, text=True, timeout=3)
        print(f"{green}~ Interrupt signal sent successfully.{reset}")
        return True
    except subprocess.TimeoutExpired:
        # sending the interrupt timed out. doesn't necessarily mean the viewer is dead.
        print(f"{red}Error: Timeout sending interrupt signal to tmux '{target_pane}'.{reset}")
        return False
    except subprocess.CalledProcessError as e:
         # the tmux command failed. check if the session/pane is gone.
         stderr_lower = e.stderr.strip().lower() if e.stderr else ""
         if "no server running" in stderr_lower or "session not found" in stderr_lower or "pane not found" in stderr_lower :
             print(f"{yellow}Warn: Target session/pane '{target_pane}' seems to be gone. Cannot send interrupt.{reset}")
             # if it's gone, update the flag.
             persistent_viewer_active = False # Viewer is confirmed gone
         else:
             # some other tmux error.
             print(f"{red}Error sending interrupt signal via tmux: {e.stderr.strip()}{reset}")
         return False
    except Exception as e:
        # unexpected python error.
        print(f"{red}Unexpected error sending interrupt signal via tmux: {e}{reset}")
        return False

# starts the special tmux viewer window in the visual terminal if it's not already running.
def launch_persistent_viewer_if_needed():
    """Launches the visual terminal + tmux viewer window if not already active."""
    global persistent_viewer_active
    # need both tmux and the terminal program.
    if not tmux_path_global or not visual_term_path_global: return False

    # first, double-check if the session *really* exists right now, even if the flag is true.
    if persistent_viewer_active and check_tmux_session(TMUX_VIEWER_SESSION_NAME):
        # print(f"{blue}~ Persistent viewer '{TMUX_VIEWER_SESSION_NAME}' already active.{reset}")
        # it exists and the flag was true, so we're good.
        return True # Already running and confirmed
    elif persistent_viewer_active:
        # the flag was true, but the session check failed. the window must have been closed.
        print(f"{yellow}Warn: Viewer flag was active, but session '{TMUX_VIEWER_SESSION_NAME}' not found. Resetting flag.{reset}")
        # reset the flag.
        persistent_viewer_active = False

    # if we reach here, we need to try launching it.
    print(f"\n{blue}~ Launching Persistent Viewer ({VISUAL_TERMINAL} + tmux session '{TMUX_VIEWER_SESSION_NAME}')...{reset}")
    # build the command to run inside the terminal.
    # it starts tmux, creates or attaches (-a) to the session, sets history limit, and disables alternate screen mode (to avoid messing up scrollback).
    # semicolons need escaping (\;) because they are passed inside a string to bash -c.
    tmux_cmd = (
        f"{tmux_path_global} new-session -A -s {TMUX_VIEWER_SESSION_NAME} \\; "
        f"set-option -t {TMUX_VIEWER_SESSION_NAME} history-limit {TMUX_HISTORY_LIMIT} \\; "
        f"set-window-option -t {TMUX_VIEWER_SESSION_NAME}:0 alternate-screen off"
    )
    # build the arguments to launch the visual terminal itself.
    # set the window title (-t) and execute (-e) the tmux command string using bash.
    term_args = [
        visual_term_path_global,
        '-T', f'AI Viewer: {TMUX_VIEWER_SESSION_NAME}', # Set window title
        '-e', f'bash -c "{tmux_cmd}"' # Execute the tmux command string in bash
    ]
    try:
        # launch the terminal in the background using popen (so our script doesn't wait for it).
        # redirect its output so it doesn't clutter our main script's terminal.
        subprocess.Popen(term_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{green}  Launched viewer process. Waiting briefly for tmux server/session to initialize...{reset}")
        # give tmux a moment to start up and then check if the session exists.
        session_found = False
        # check a few times with pauses, just to be robust.
        for attempt in range(4): # Check up to 4 times over ~4 seconds
            time.sleep(1.1) # Give it a moment to start
            if check_tmux_session(TMUX_VIEWER_SESSION_NAME):
                # found it.
                session_found = True
                break
            # print(f"{blue}  Still waiting... (attempt {attempt+1}){reset}") # Optional verbose wait

        if session_found:
            # success. the viewer is running.
            print(f"{green}  Viewer session '{TMUX_VIEWER_SESSION_NAME}' confirmed active.{reset}")
            # set the global flag to true.
            persistent_viewer_active = True
            # give the user a hint about how to scroll in the tmux window.
            print(f"\n{cyan}--- VIEWER INFO: Use Ctrl+b then '[' to enter scroll mode (PgUp/PgDn/Arrows), 'q' to exit scroll mode ---{reset}")
            return True
        else:
            # we launched the terminal, but the tmux session didn't appear. something went wrong.
            print(f"{red}  Error: Failed to verify tmux session '{TMUX_VIEWER_SESSION_NAME}' started after launching the terminal.{reset}")
            print(f"{yellow}  Check if '{VISUAL_TERMINAL}' supports the '-e' flag correctly or if tmux is configured properly.{reset}")
            # ensure the flag is false.
            persistent_viewer_active = False # Ensure flag is false
            return False
    except Exception as e:
        # an error occurred trying to launch the terminal process itself.
        print(f"{red}Error launching persistent viewer terminal: {e}{reset}")
        # show the command arguments for debugging help.
        print(f"{red}Arguments used: {' '.join(term_args)}{reset}") # Show command for debugging
        # ensure the flag is false.
        persistent_viewer_active = False # Ensure flag is false
        return False

# opens a *new* terminal window just for one command, and tries to keep it open afterwards.
def run_visual_pause_window(command_to_execute):
    """
    Runs command visually in a NEW separate terminal window that PAUSES before closing.
    (Method 1: Using --hold)
    """
    # need the path to the visual terminal.
    if not visual_term_path_global:
        print(f"{red}Error: Path to '{VISUAL_TERMINAL}' is not set. Cannot launch separate window.{reset}")
        return False

    # 1. escape single quotes within the ai's command, as it will be wrapped in single quotes for 'sh -c'.
    escaped_command = command_to_execute.replace("'", "'\\''")

    # 2. create the command string to run inside the terminal. just the escaped ai command.
    # we rely on the terminal's '--hold' flag to keep the window open, rather than adding 'read' or 'pause'.
    command_inside_terminal = f"sh -c '{escaped_command}'"
    # Alternatively, maybe even skip sh -c if the command is simple and doesn't need shell features?
    # command_inside_terminal = escaped_command # <-- Might work for simple commands ONLY

    # 3. prepare the arguments for popen: terminal executable, the --hold flag, the execute flag (-e), and the command string.
    # note: make sure the specific terminal actually supports '--hold'.
    args_for_popen = [visual_term_path_global, "--hold", "-e", command_inside_terminal]

    try:
        print(f"{gold}~ Opening NEW terminal window (using --hold). Command:{reset} {purple}{command_to_execute}{reset}")
        # --- Optional Debugging ---
        # print(f"{cyan}Args for Popen:{reset} {args_for_popen}")
        # --- End Debugging ---

        # launch the terminal in the background.
        process = subprocess.Popen(args_for_popen, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{green}  Launched separate window process (PID: {process.pid}). It should remain open after command finishes.{reset}")
        print(f"{yellow}  NOTE: You will likely need to manually close this window; it may not wait for 'Enter'.{reset}")
        return True
    except FileNotFoundError:
         # the terminal executable itself wasn't found.
         print(f"{red}Error launching separate window: Command '{visual_term_path_global}' not found.{reset}")
         return False
    except Exception as e:
        # some other error occurred during launch. check if it looks like '--hold' wasn't recognized.
        if "unrecognized option '--hold'" in str(e).lower() or "invalid option" in str(e).lower():
             print(f"{red}Error: Your '{VISUAL_TERMINAL}' may not support the '--hold' option.{reset}")
        else:
             # generic launch error.
             print(f"{red}Error launching separate visual '{VISUAL_TERMINAL}' window: {e}{reset}")
        # show the arguments used for debugging.
        print(f"{red}Arguments used: {args_for_popen}{reset}")
        return False

# --- Function to Handle Command Execution ---
# (Keep the existing handle_command_execution function)
# this function takes the ai's command and runs it according to the chosen mode (persistent or separate). it also logs the command.
def handle_command_execution(ai_generated_command, primary_mode, execution_mode, user_input_request):
    """Logs command, then runs the AI_GENERATED_COMMAND based on execution_mode."""
    # figure out a user-friendly name for the execution mode for logging.
    exec_mode_friendly = "Persistent" if execution_mode == "persistent_single_viewer" else "Separate"
    # combine primary mode and execution mode for the log entry.
    log_mode_info = f"{primary_mode.capitalize()}/{exec_mode_friendly}"
    try:
        # find the directory where this script is running.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # define the log file path in the same directory.
        log_path = os.path.join(script_dir, "ai_cmd_x_history.log")
        # open the log file in append mode ('a') with utf-8 encoding.
        with open(log_path, "a", encoding='utf-8') as f:
            # get the current timestamp.
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # escape single quotes in the request and command just to make the log file cleaner.
            safe_request = user_input_request.replace("'", "\\'")
            safe_command = ai_generated_command.replace("'", "\\'")
            # write the log entry.
            f.write(f"[{ts}] Mode: {log_mode_info}, Request: '{safe_request}', Running: '{safe_command}'\n")
    except Exception as e: 
        # print an error if logging fails, but don't stop the script.
        print(f"{red}Log write error to {log_path}: {e}{reset}")

    # --- Execute based on mode ---
    # check if we're in persistent viewer mode.
    if execution_mode == "persistent_single_viewer":
        print(f"{blue}--- Persistent Mode Execution ---{reset}")
        # make sure the viewer window is running (launch it if needed).
        viewer_ready = launch_persistent_viewer_if_needed()
        if viewer_ready:
            # if the viewer is ready, send the command to it.
            print(f"{blue}~ Sending command to persistent viewer: {purple}{ai_generated_command}{reset}")
            if not send_command_to_tmux_viewer(TMUX_VIEWER_SESSION_NAME, ai_generated_command):
                # report if sending the command failed.
                print(f"{red}Failed to send command to persistent viewer (it might be closed or unresponsive).{reset}")
        else:
            # report if the viewer couldn't be started or found.
            print(f"{red}Error: Persistent viewer is not ready. Command '{ai_generated_command}' was not sent.{reset}")
        print(f"{blue}-------------------------------{reset}")

    # check if we're in separate window mode.
    elif execution_mode == "separate_pause_window":
        print(f"{blue}--- Separate Mode Execution ---{reset}")
        # call the function designed to launch a command in a new, pausing window.
        if not run_visual_pause_window(ai_generated_command):
            # report if the launch function itself returned an error.
            print(f"{red}Error occurred during the separate window launch process.{reset}")
        # run_visual_pause_window prints its own success/details
        print(f"{blue}-----------------------------{reset}")
    else:
        # this shouldn't happen if the mode selection logic is correct.
        print(f"{red}Internal Error: Unknown execution mode '{execution_mode}' in handle_command_execution.{reset}")


if __name__ == "__main__":
    # ==================================
    # === MAIN PROGRAM STARTS HERE ===
    # ==================================
    # ok, let's get things rolling.
    # --- Initial Setup ---
    print(f"{purple}--- Starting Ai-Terminal-X Assistant ---{reset}")
    # first, get the api key (exits if it fails).
    api_key = load_api_key()        # Exits if key not found/entered
    # next, configure the connection to the ai (exits if it fails).
    ai_model = configure_ai(api_key) # Exits if connection fails
    # then, check if the required external tools are installed (exits if not).
    check_external_tools() # exits if tools not installed properly

    # --- Define and Print Banner ---
    # show a cool startup banner.
    banner = fr""" {green}
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⡴⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                    {gold}Ai-Terminal-X{reset}{green}      ⢀⣠⣴⣿⠟⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣶⣿⣿⣿⡅⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣀⣀⣀⣀⣀⣀⣀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣤⣤⣤⣤⣴⣿⣿⣿⣿⣯⣤⣶⣶⣾⣿⣶⣶⣿⣿⣿⣿⣿⡿⠿⠟⠛⠉⠉⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠐⠉⠁⠈⣹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⠶⠶⠦⠄⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣾⡿⠟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⡀⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣾⣿⣟⣡⣤⣾⣿⣿⣿⣿⣿⣿⢏⠉⠛⣿⣿⣿⣿⣿⣿⣿⣿⣿⡻⢿⣿⣿⣦⡀⠀⠀⠀⠀⠀ 
                    ⠀⠀⠀⠀⠀⣀⣤⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠈⠻⡄⠁⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠈⠙⠻⣿⣆⠀⠀⠀⠀
                    ⠀⠀⠀⠀⢰⣿⣿⣿⣿⡿⠛⠉⠉⠉⠛⠛⠛⠛⠋⠁⠀⠀⠀⠁⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠈⠙⢧⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠙⠿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣤⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠁⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠙⣿⣿⣿⣷⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⢀⣤⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⢹⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⢀⣤⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠋⠁⠀⠀⠀⠀⠈⣿⣿⡟⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠛⢋⣩⡿⠿⠿⠟⠛⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡟⠁⠀⠀⠀{reset}{gold}Developed By{reset}{green}
                    ⠀⢀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⣄⣀⡀⠀⠀⠀⠀⠀⠐⠉⠀⠀{reset}{gold}Muhammad Izaz Haider{reset}{green}
                    ⠀⣾⣿⣿⣿⣿⣿⣿⣿⠻⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠻⢿⣶⣤⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                    ⢰⣿⣿⣿⣿⣿⣿⣿⣿⡄⠙⢿⣄⠀⠀⠀⠀⠀⠀⠀⠀⠠⣤⣀⠀⠀⠀⠠⣄⣀⣀⡉⢻⣿⣿⣿⣶⣄⡀⠀⠀⠀⠀⠀⠀⠀
                    ⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿⣦⣤⣤⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣄⡀⠀⠀⠀⠀
                    ⠀⢻⡟⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠛⠛⠋⠉⠀⠀⢀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠀⠀
                    ⠀⠀⠃⠀⢹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠁⠀⠀⠀⠀⠀⠈⠉⡿⢿⣿⣿⣿⣷⡄⠀
                    ⠀⠀⠀⠀⢸⣿⣿⡟⠙⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠿⠛⠛⣿⣿⣿⣿⣿⣧⣀⣀⡄⠀⢠⠀⠀⡀⠁⠘⣿⡿⣿⣿⣷⠀
                    ⠀⠀⠀⠀⢸⣿⡿⠁⠀⠀⠀⠙⠻⠿⣟⠻⢿⣿⣿⣿⣷⣦⡀⠀⠈⠻⢿⣿⣿⣭⣉⡉⠀⠀⠐⠀⠀⠀⠠⠀⠚⠀⠸⣿⣿⡄
                    ⠀⠀⠀⠀⣸⡟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⢿⣿⣿⣦⡀⠀⠀⠀⠉⠉⠉⠉⠉⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠁
                    ⠀⠀⠀⠠⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⢿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡟⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⠟⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠀⠀⠀
                {cyan}========================================================={reset}
                {blue} AI Assisted Linux Terminal Assistant {reset}|{gold} Revolution Begins {reset}
                {cyan}========================================================={reset}"""
    print(banner)

    # --- Main Loop ---
    # the main loop that keeps asking the user for input until they quit.
    while True:
    
        # --- Stage 1: Select Primary Mode ---
        # first, figure out what the user wants to do (quick, interactive, suggest, or exit).
        primary_mode = None
        # keep asking until they pick a valid mode.
        while primary_mode is None:
        
            print(f"\n>>>> Choose Operating Mode <<<<\n")
            print(f" {gold}[1] Quick Mode{reset}\t\t{blue}(AI generates command -> Risk Check -> Run if safe / Confirm if risky){reset}")
            print(f" {gold}[2] Interactive Mode{reset}\t{blue}(AI generates command -> Risk Check -> Ask Run/Copy/Cancel){reset}")
            # --- NEW/MODIFIED ---
            print(f" {gold}[3] Command Suggester{reset}\t{blue}(AI suggests multiple commands for a task -> Display options){reset}")
            print(f" {gold}[4] Exit{reset}\t\t\t{blue}(Quit the application){reset}")
            choice1 = input(f"\n>>>> {green}Enter choice [1-4]: {reset}").strip()
        
            # set the primary_mode based on their choice.
            if choice1 == "1":
                primary_mode = "quick"
            elif choice1 == "2": 
                primary_mode = "interactive"
        
            # --- NEW/MODIFIED ---
            elif choice1 == "3": 
                primary_mode = "suggester"
            elif choice1 == "4":
                # if they choose 4, exit the whole script.
                print(f"\n{red}Exiting Ai-Terminal-X. Goodbye!{reset}") 
                sys.exit(0)
            else:
                # invalid choice, loop will ask again.
                print(f"{red}Invalid choice. Please enter 1, 2, 3, or 4.{reset}")

        # --- Stage 2: Select Execution Mode (Only if NOT Suggester Mode) ---
        # --- NEW/MODIFIED --- (Conditional execution style selection)
        # if they chose quick or interactive, ask *how* they want commands run (persistent or separate window).
        execution_mode = None
        exec_mode_friendly = None
    
        # only ask for execution style if we are in quick or interactive mode.
        if primary_mode in ["quick", "interactive"]:
            # this function will loop until they give a valid choice (1 or 2).
            execution_mode = select_execution_mode() # This function loops until valid input
        
            # get a nice name for the chosen execution mode.
            exec_mode_friendly = "Persistent Viewer" if execution_mode=="persistent_single_viewer" else "Separate Window"
        
            # confirm the selected modes to the user.
            print(f"\n{blue}>>> Mode Selected: {reset}{gold}{primary_mode.capitalize()}{reset} {blue}with {reset}{gold}{exec_mode_friendly}{reset} {blue} Execution <<<{reset}")
        
            # Provide context-specific instructions based on execution mode.
            if execution_mode == "persistent_single_viewer":
                print(f"{green}\n>>>>Enter command. {red}Use Ctrl+C{reset} {green}here to interrupt running command | You can scroll in persistent mode by pressing{gold} ctrl + B then [{reset} {blue}ok.{reset}")
            else: # Separate Window mode
                print(f"{blue}\n>>>>Enter your command request. Each command will open in a new window that pauses.{reset}")
       
            # remind them of the control commands.
            print(f"{gold}Type {reset}' explain <topic>/<command> '{green} for explanations, {reset}' back '{blue} to change modes, {reset}' quit '{red} to exit.{reset}")

        elif primary_mode == "suggester":
            # suggester mode doesn't need an execution style. just print a banner and instructions.
            banner3 = f"""{blue}
                    ───▄▀▀▀▄▄▄▄▄▄▄▀▀▀▄───  {gold}Cool...I will give the Perfect Commands{reset}{blue}
                    ───█▒▒░░░░░░░░░▒▒█─── 
                    ────█░░█░░░░░█░░█────  {reset}"Learn, Practice and Master...You can do it.."{blue}
                    ─▄▄──█░░░▀█▀░░░█──▄▄─
                    █░░█─▀▄░░░░░░░▄▀─█░░█
                    {reset}
                """
            print(f"\n{banner3}")
            print(f"\n{blue}>>> Mode Selected: {reset}{gold}Command Suggester{reset} {blue} <<<{reset}")
            print(f"{green}\n>>>>Enter a task description{reset}{green} (e.g., 'find large files', 'check network connections'){reset}")
            print(f"{gold}Type {reset}' back '{blue} to change modes, {reset}' quit '{red} to exit.{reset}")


        # --- Inner Loop: Handle User Requests within the selected mode ---
        # now we're in a specific mode, keep handling requests until they type 'back' or 'quit'.
        while True:
            # STEP 1: Get User Input
            # --- NEW/MODIFIED --- (Prompt based on mode)
            # get the command request or control command from the user.
            # display a prompt that shows the current mode.
            if primary_mode == "suggester":
                 prompt_display = f"\nAi-Terminal-X (Expert Command Suggester)</> : "
             
            else: # Quick or Interactive
                 prompt_display = f"\nAi-Terminal-X ({primary_mode.capitalize()}/{exec_mode_friendly})</> :  "

            try:
                # wait for the user to type something and press enter.
                user_input = input(prompt_display).strip()
            except KeyboardInterrupt: # Catch Ctrl+C in *this* terminal (where Ai-Terminal-X runs)
                # handle ctrl+c press in the main script's terminal.
                print() # Newline after ^C
                # --- NEW/MODIFIED --- (Interrupt logic applies only to persistent mode)
                # if we are in persistent mode and the viewer is active, try to interrupt the command inside the viewer.
                if primary_mode in ["quick", "interactive"] and execution_mode == "persistent_single_viewer" and persistent_viewer_active:
                    # Try to interrupt the command running *inside* the persistent viewer
                    if send_interrupt_to_tmux_viewer(TMUX_VIEWER_SESSION_NAME):
                         print(f"{yellow}Interrupt (Ctrl+C) signal sent to persistent viewer. The command inside might take a moment to stop.{reset}")
                    else:
                         print(f"{red}Failed to send interrupt signal to the viewer (it might be closed or unresponsive).{reset}")
                    # remind them they can enter another command or control word.
                    print(f"{cyan}You can enter your next request, '{purple}back{cyan}', or '{purple}quit{cyan}'.{reset}")
                    # continue to the next iteration of this inner loop, waiting for input again.
                    continue # Continue inner loop, ready for next input
                else:
                    # if not in persistent mode, or viewer isn't active, ctrl+c here just exits the main script.
                    print(f"\n{red}Ctrl+C detected. Exiting Ai-Terminal-X.{reset}")
                    sys.exit(0)
            except EOFError: # Catch Ctrl+D
                # handle ctrl+d (end of file), treat it as quitting.
                print(f"\n{red}EOF detected. Exiting Ai-Terminal-X.{reset}")
                sys.exit(0)

            # save the original input for logging purposes.
            original_request = user_input # Keep original for logging/prompts

            # --- Handle Control Commands FIRST (Common to all modes) ---
            # check for special commands like 'quit' or 'back' first.
            # ignore completely empty input.
            if not user_input: continue # Ignore empty input

            # convert input to lowercase for easier checking of control commands.
            user_input_lower = user_input.lower()

            # check for quit commands.
            if user_input_lower in ["quit", "exit"]:
                print(f"\n{red}Exiting Ai-Terminal-X as requested. Goodbye!{reset}")
                sys.exit(0)
            # check for the 'back' command.
            if user_input_lower == "back":
                print(f"{blue}\n<<< Returning to Mode Selection...{reset}")
                # if the persistent viewer was active, warn the user it might still be running in the background.
                if primary_mode in ["quick", "interactive"] and execution_mode == "persistent_single_viewer" and persistent_viewer_active:
                     print(f"{yellow}Note: The Persistent viewer session '{TMUX_VIEWER_SESSION_NAME}' may still be open in its own window.{reset}")
                     # Consider asking if they want to kill it? For simplicity, we won't auto-kill now.
                # break out of this inner loop to go back to the outer mode selection loop.
                break # Exit this inner loop to go back to the outer mode selection loop

            # --- === Mode-Specific Logic === ---

            # --- NEW/MODIFIED --- (Suggester Mode Block)
            # --- if in suggester mode ---
            if primary_mode == "suggester":
                # any input that isn't a control command is treated as a task description.
                task_description = original_request
                # find the path to the command suggester helper script.
                script_dir = os.path.dirname(os.path.abspath(__file__))
                suggester_script_path = os.path.join(script_dir, COMMAND_SUGGESTER_SCRIPT)

                # make sure the helper script actually exists.
                if not os.path.exists(suggester_script_path):
                     print(f"\n{red}Error: Cannot find the command suggester script '{COMMAND_SUGGESTER_SCRIPT}'.{reset}")
                     print(f"{red}Please ensure '{COMMAND_SUGGESTER_SCRIPT}' is in the same directory as this script ({script_dir}).{reset}")
                     # go back and ask for input again.
                     continue # Ask for input again in suggester mode

                print(f"\n{blue}--- Asking AI for Suggestions via Helper Script ---{reset}")
                print(f"{cyan}Task: {task_description}{reset}")
                try:
                    # run the helper script using the same python interpreter that's running this script.
                    # pass the task description as a command-line argument to the helper script.
                    args = [sys.executable, suggester_script_path, task_description]

                    # run the helper script, wait for it to finish, capture its output (stdout and stderr).
                    # use check=false so we can handle non-zero exit codes manually.
                    result = subprocess.run(args, capture_output=True, text=True, check=False, encoding='utf-8')

                    # print the standard output from the helper script (this should be the suggestions).
                    if result.stdout:
                        print(result.stdout.strip()) # Display the suggestions
                    else:
                        # if there's no stdout, maybe it only printed errors.
                        print(f"{yellow}Suggestion script produced no standard output.{reset}")

                    # check if the helper script finished with an error code.
                    if result.returncode != 0:
                        print(f"\n{red}--- Error From Suggester Script ---{reset}")
                        print(f"{red}The suggester script ({COMMAND_SUGGESTER_SCRIPT}) exited with error code {result.returncode}.{reset}")
                        # if there was error output (stderr), print that too.
                        if result.stderr:
                             print(f"{yellow}Suggester Script Error Output:{reset}\n{result.stderr.strip()}")
                        else:
                             print(f"{yellow}(No specific error message provided by the suggester script on stderr){reset}")
                        print(f"{red}---------------------------------{reset}")

                except FileNotFoundError:
                     # this would mean python itself wasn't found, which is very unlikely.
                     print(f"{red}Critical Error: Could not execute Python interpreter '{sys.executable}'. Is Python installed correctly?{reset}")
                except Exception as e:
                     # catch any other unexpected errors during the subprocess call.
                     print(f"{red}An unexpected error occurred while trying to run the suggester script: {e}{reset}")

                # after running the suggester, just continue the inner loop to ask for the next task.
                continue # After showing suggestions, prompt for the next task in Suggester mode

            # --- Quick and Interactive Mode Logic ---
            # --- NEW/MODIFIED --- (Encapsulated in elif)
            # --- if in quick or interactive mode ---
            elif primary_mode in ["quick", "interactive"]:

                # --- Handle Explanation Requests (Only in Quick/Interactive) ---
                # check if the user input starts with "explain", "what is", etc.
                explain_triggered, topic_to_explain, matched_prefix = detect_explain_request(user_input)

                # if it was an explanation request...
                if explain_triggered:
                    # ...but they gave no topic after the prefix.
                    if topic_to_explain is None:
                        print(f"{yellow}Please specify what you want explained after '{matched_prefix.strip()}'.{reset}")
                    # ...and they provided a topic...
                    if topic_to_explain: # Only ask AI if we have a valid topic
                        print(f"\n{blue}-------------- Getting Explanation --------------{reset}")
                        # ...ask the ai for an explanation.
                        explanation_text = explain_command(ai_model, topic_to_explain)
                        # print the explanation nicely formatted.
                        print(f"\n{gold}AI Explanation:\n{reset}")
                        print(explanation_text) # Assumes explain_command includes color for errors
                        print(f"{gold}--------------------------------------------------{reset}")
                    # after handling the explain request (or invalid explain), go back to ask for new input.
                    continue # Go to next prompt asking for input (skip command generation)

                # --- Process Standard Command Request (Quick/Interactive) ---
                # if it wasn't an explain request, it must be a request for a command.
                # STEP 2: AI Command Generation
                print(f"\n--- Generating Command ---")
                # ask the ai to generate the command and explanation for the user's original request.
                command_from_ai, explanation_from_ai, error_msg = gemini_command_and_explanation(ai_model, original_request)

                # if there was an error getting the command (api error, parsing error, safety block)...
                if error_msg:
                    print(error_msg) # Display error from AI comms/parsing
                    # ...go back and ask for new input.
                    continue # Ask for new input
                # also double-check if the command itself is empty (should be caught by error_msg).
                if not command_from_ai:
                    print(f"{red}AI did not provide a valid command.{reset}")
                    continue # Ask for new input

                # STEP 3: Display AI Suggestion
                # show the user what the ai came up with.
                print(f"\n{gold}>>>{blue} Hayy Look Here ... {yellow}AI Suggests:{reset} {command_from_ai}") # Print command prominently
            
                # if there was an explanation, show that too.
                if explanation_from_ai:
                    print(f"{gold}>>> {blue}Kindly Look at also {yellow}Explanation: {reset} {explanation_from_ai}")
                else:
                    # mention if no explanation was found.
                    print(f" {yellow}Awww....(No explanation provided/parsed from AI){reset}")

                # STEP 4: AI Risk Check
                # check if the ai thinks the command is risky.
                print(f"\n{gold}>>> {green}Wait Safety Matters...{blue} Checking Command Risk...{reset}")
                risk_explanation = validate_command_risk(ai_model, command_from_ai)

                # STEP 5: Display Risk Assessment
                # determine if it's risky based on whether validate_command_risk returned an explanation.
                is_risky = bool(risk_explanation)
                if is_risky:
                     # use a stronger warning if the risk check itself failed or was blocked.
                     if "treat as potentially risky" in risk_explanation:
                         print(f"{yellow}\n‼ {red}CAUTION: AI RISK CHECK FAILED/BLOCKED!{reset}")
                         print(f"{yellow}   Reason: {risk_explanation}{reset}")
                         print(f"{yellow}   Treat the command as potentially dangerous.{reset}")
                     else:
                         # standard warning for a command assessed as risky.
                         print(f"{yellow}\n>>> ‼ {red}RISKY COMMAND DETECTED!{reset}")
                         print(f"\n{gold}>>>{green}   AI Risk Assessment: {yellow} {risk_explanation}{reset}")
                else:
                     # the command was assessed as safe.
                     print(f"{blue}~~~ Command assessed as safe by AI .{reset}")

                # STEP 6: Execution Decision (Based on primary_mode)
                # decide whether to run the command based on the mode (quick/interactive) and risk.
                run_now = False
                cancel_action = False

                # get a description of *how* it will be executed for the prompts.
                exec_desc = f"in {exec_mode_friendly}" # e.g., "in Persistent Viewer"

                # --- quick mode logic ---
                if primary_mode == "quick": # QUICK MODE - Only ask confirmation for risky commands
                    if is_risky:
                        # if risky, ask the user for confirmation (y/n).
                        while True:
                            confirm = input(f"{red}\n Execute this risky command {exec_desc}? (y/n): {reset}").lower().strip()
                            if confirm in ['y', 'yes']:
                                # user said yes.
                                print(f"{blue}Okay, proceeding with execution...{reset}")
                                run_now = True
                                break
                            elif confirm in ['n', 'no']:
                                # user said no.
                                print(f"{gold}~ Execution cancelled by user.{reset}")
                                cancel_action = True
                                break
                            else:
                                # invalid input, ask again.
                                print(f"{yellow}Invalid input. Please enter 'y' or 'n'.{reset}")
                    else:
                        # if safe in quick mode, run it automatically.
                        print(f"{gold}\n (Quick Mode) Automatically running safe command {exec_desc}...{reset}")
                        run_now = True

                # --- interactive mode logic ---
                elif primary_mode == "interactive": # INTERACTIVE MODE - Always ask for action
                    # always ask the user what to do: run, copy (if available), or cancel.
                    # build the options string dynamically.
                    options = f"y=Run {exec_desc}"
                    # check if xclip was found earlier.
                    copy_option_available = xclip_path_global is not None
                    if copy_option_available:
                        # only add the copy option if xclip is available.
                        options += ", c=Copy Command"
                    options += ", n=Cancel"
                    print("\n")
                    # keep asking until they choose a valid action.
                    while True:
                        action = input(f"{green}\n Action? ({options}): {reset}").lower().strip()

                        if action in ["y", "yes"]:
                            # user chose to run.
                            run_now = True
                            break
                        # only accept 'c' if the copy option is actually available.
                        elif copy_option_available and action in ["c", "copy"]:
                            try:
                                # try to copy the command to the clipboard using xclip.
                                # use popen and communicate to send the command text to xclip's input.
                                p = subprocess.Popen([xclip_path_global, '-selection', 'clipboard'], stdin=subprocess.PIPE, text=True, encoding='utf-8')
                                stdout, stderr = p.communicate(input=command_from_ai, timeout=5)
                                # check if xclip ran successfully.
                                if p.returncode == 0:
                                     print(f"{green}\n Command copied to clipboard!{reset}")
                                     # print(f"{purple}   {command_from_ai}{reset}") # Optionally show again
                                else:
                                     # xclip failed, report the error code and any stderr output.
                                     error_detail = f" Stderr: {stderr.strip()}" if stderr else ""
                                     print(f"{red}Copy failed. xclip exited with code {p.returncode}.{error_detail}{reset}")
                            except subprocess.TimeoutExpired:
                                # xclip took too long.
                                print(f"{red}Copy failed: Timeout waiting for xclip.{reset}")
                            except FileNotFoundError:
                                 # xclip wasn't found (shouldn't happen if initial check passed).
                                 print(f"{red}Copy failed: Command 'xclip' not found? This shouldn't happen if check_external_tools worked.{reset}")
                            except Exception as e:
                                # some other error during the copy attempt.
                                print(f"{red}Copy failed with unexpected error: {e}{reset}")
                            # copying means we don't run the command now.
                            cancel_action = True # Copying implies we don't run it now
                            break
                        elif action in ["n", "no", "cancel"]:
                            # user chose to cancel.
                            print(f"{gold}\n~ Action cancelled by user.{reset}")
                            cancel_action = True
                            break
                        else:
                            # invalid input, remind them of the valid options.
                            print(f"{yellow}Invalid input. Please choose from the available options ({options}).{reset}")

                # STEP 7: Execute Command (If Approved in Step 6)
                # if the logic above decided we should run the command...
                if run_now:
                    # ...call the execution handler function.
                    handle_command_execution(command_from_ai, primary_mode, execution_mode, original_request)
                elif cancel_action:
                    # if the action was cancelled or they chose copy, do nothing here.
                    pass # Do nothing further, loop will ask for next input
                else:
                    # this state shouldn't normally be reached.
                    print(f"{yellow}Internal warning: Command action was not decided. Not running command.{reset}")

            # --- End of mode-specific logic ---

    # --- End of Main Loop ---
    # just a final message if the script somehow exits the main loop normally (shouldn't really happen).
    print(f"\n{purple}Ai-Terminal-X loop ended.{reset}")