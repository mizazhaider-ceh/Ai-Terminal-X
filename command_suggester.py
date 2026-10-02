#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# === Command Suggester Script ===
# Purpose: This helper script talks to the Google AI to get Linux command
#          suggestions based on a task you describe. It then cleans up
#          the AI's answer and prints it out clearly.
# How it's used: The main Ai-CMD-X script runs this one when you choose
#               the "Command Suggester" mode.

# --- 1. Importing Toolkits (Libraries) ---
# These lines bring in pre-written code tools that help us do things.
import google.generativeai as genai # The main toolkit for talking to Google's AI
import os                          # Tools for interacting with the operating system (like finding file paths)
from dotenv import load_dotenv     # A tool to load secret information (like API keys) from a special file
import sys                         # Tools for interacting with the Python system itself (like handling arguments or exiting)
import re                          # A toolkit for finding text patterns (a bit advanced, but useful here!)

# --- 2. Setting Up Colors (Optional but Nice) ---
# These are codes that make text appear in different colors in the terminal.
# It helps make the output easier to read.
red = "\033[91m"; green = "\033[32m"; blue = "\033[94m"; purple = "\033[95m"
gold = "\033[38;5;220m"; cyan = "\033[36m"; yellow = "\033[93m"; reset = "\033[0m"
# 'reset' changes the color back to normal.

# --- 3. Configuration (Settings) ---
API_KEY_FILENAME = ".env" # The name of the secret file where we expect to find the API key.
AI_MODEL_NAME = "gemini-2.0-flash" # The Gemini model used for suggestions.

# --- 4. Recipe: Loading Your Secret API Key ---
# This defines a reusable set of instructions (a function) called 'load_api_key'.
# Think of the API key like a password to use the Google AI service.
def load_api_key():
    """
    Finds and reads your Google AI password (API Key) from the '.env' file.
    If it can't find the file or the key inside, it prints an error and stops.
    """
    # Figure out where this script is located on your computer
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Create the full path to the '.env' file in the same directory
    dotenv_path = os.path.join(script_dir, API_KEY_FILENAME)

    # Check if the '.env' file actually exists where we expect it
    if not os.path.exists(dotenv_path):
         # If not, print an error message (to the special 'stderr' channel)
         print(f"{red}Error: Secret file '{API_KEY_FILENAME}' not found here: {script_dir}{reset}", file=sys.stderr)
         # Stop the script because we can't continue without the key
         sys.exit(1) # The '1' tells the computer something went wrong

    # Use the 'dotenv' toolkit to load the information from the file
    load_dotenv(dotenv_path=dotenv_path)
    # Try to get the specific key named "GEMINI_API_KEY" from the loaded info
    api_key = os.getenv("GEMINI_API_KEY")

    # Check if we actually got a key (it might be missing from the file)
    if not api_key:
        # If no key was found, print an error explaining how the file should look
        print(f"{red}Error: 'GEMINI_API_KEY' was not found inside the file '{dotenv_path}'.{reset}", file=sys.stderr)
        print(f"{yellow}Make sure the file has a line like: GEMINI_API_KEY=YOUR_REAL_API_KEY{reset}", file=sys.stderr)
        # Stop the script
        sys.exit(1)

    # If we got the key successfully, send it back to whoever called this recipe
    return api_key

# --- 5. Recipe: Setting Up the Connection to the AI Brain ---
# This function connects to Google AI using your key.
def configure_ai(api_key):
    """
    Uses your API key to connect to Google AI and get ready to chat.
    If it fails (maybe bad key, no internet), it prints an error and stops.
    """
    try: # We 'try' this because connecting might fail
        # Tell the Google AI toolkit about your key
        genai.configure(api_key=api_key)
        # Choose the specific AI model (like choosing a specific brain) we want to talk to
        # 'gemini-2.0-flash' is a good, fast choice.
        model = genai.GenerativeModel(AI_MODEL_NAME)
        # If successful, send the ready-to-use model back
        return model
    except Exception as e: # If anything went wrong in the 'try' block...
        # Print a detailed error message
        print(f"{red}Error connecting to Google AI: {e}{reset}", file=sys.stderr)
        # Give hints based on common errors
        if "api key not valid" in str(e).lower():
             print(f"{red}Your API Key seems incorrect. Double-check '{API_KEY_FILENAME}'.{reset}", file=sys.stderr)
        elif "permission" in str(e).lower():
             print(f"{red}Looks like a permission problem. Is your API key properly enabled on the Google website?{reset}", file=sys.stderr)
        else:
             print(f"{yellow}This might be an internet problem or a temporary issue with Google's servers.{reset}", file=sys.stderr)
        # Stop the script because we can't talk to the AI
        sys.exit(1)
# --- Define the AI Prompt for Suggestions (REVISED FOR EXPERTISE/ACCURACY) ---
# This prompt guides the AI to provide output in a specific, parsable format,
# while emphasizing the need for accurate and reliable commands.
suggester_prompt = """
You are an **Expert Linux System Administrator AI Assistant**. Your primary goal is to provide **highly accurate, effective, and reliable** Linux Bash commands to solve the user's specified task. Prioritize standard, commonly available utilities and correct syntax. Ensure the commands are practical and directly address the user's need.

Task: {USER_TASK}

Instructions:
1.  Provide exactly THREE distinct, **syntactically correct, and runnable** Linux Bash commands relevant to the task. Choose commands that are generally considered good practice.
2.  For EACH of the three commands, provide a clear and concise one-sentence explanation starting EXACTLY with "Explanation: ". Briefly mention the purpose of key options if crucial for understanding.
3.  Evaluate the three suggestions based on typical use cases, reliability, and simplicity. Identify the SINGLE command you **most strongly recommend** as the standard or most direct working solution.
4.  Format your output STRICTLY like the example below. Use Markdown backticks (`) around commands. Do NOT add any introductory text, summaries, warnings, or closing remarks. **Accuracy and adherence to format are paramount.**

Example Format:
1. `grep -ri 'search_pattern' /path/to/dir`
Explanation: Recursively searches for 'search_pattern' case-insensitively within files in the specified directory.
2. `find /path/to/dir -type f -iname '*pattern*' -print`
Explanation: Finds files (case-insensitive) matching '*pattern*' within the directory and prints their names.
3. `awk '/search_pattern/{print $0}' /path/to/file.log`
Explanation: Scans 'file.log' line by line and prints lines containing 'search_pattern'.
Recommended: `grep -ri 'search_pattern' /path/to/dir`
Explanation: Recursively searches for 'search_pattern' case-insensitively within files in the specified directory.

Now, generate the expert response for the user's task, ensuring the commands are accurate and the format is perfect.
"""

# --- 7. Recipe: Understanding the AI's Answer (Parsing) ---
# This function takes the raw text answer from the AI and tries to pull out
# the separate commands and explanations based on the format we asked for.
def parse_suggestions(ai_text):
    """
    Reads the AI's text response and tries to find the commands and explanations.
    It uses the 're' toolkit (regular expressions) to look for the specific patterns.
    Returns:
        - suggestions: A list containing each suggestion (command + explanation).
        - recommended: The command and explanation the AI recommended.
        - error_msg: A message if parsing failed, otherwise None.
    """
    suggestions = [] # An empty list to hold the suggestions we find
    recommended = {"command": None, "explanation": None} # Placeholders for the recommendation

    # Clean up the AI's text a bit first
    ai_text = ai_text.strip()

    # --- Using the 're' pattern finder ---
    # This pattern looks for lines starting with a number, period, space,
    # then a command in backticks (` `), followed by a newline, and then
    # a line starting with "Explanation: ". It's like giving 're' a blueprint.
    suggestion_pattern = re.compile(r"^\s*(\d+)\.\s*`(.+?)`\s*\nExplanation:\s*(.+)", re.MULTILINE)
    # Find all parts of the text that match this blueprint
    matches = suggestion_pattern.findall(ai_text)

    # Go through each match found
    for num_str, cmd, expl in matches:
        # Add the found command and explanation to our suggestions list
        suggestions.append({
            "number": int(num_str), # Keep the number just in case
            "command": cmd.strip(), # .strip() removes extra spaces
            "explanation": expl.strip()
        })

    # Make sure suggestions are in the order 1, 2, 3...
    suggestions.sort(key=lambda item: item["number"])

    # Now, look for the "Recommended:" line using another pattern blueprint
    recommended_pattern = re.compile(r"^Recommended:\s*`(.+?)`\s*\nExplanation:\s*(.+)", re.MULTILINE)
    rec_match = recommended_pattern.search(ai_text) # Search for the first match

    if rec_match:
        # If we found the "Recommended:" line, grab the command and explanation
        recommended["command"] = rec_match.group(1).strip()
        recommended["explanation"] = rec_match.group(2).strip()
    elif suggestions:
        # If we didn't find "Recommended:" but *did* find suggestions,
        # just guess that the first suggestion is the recommended one (Plan B).
        recommended = suggestions[0].copy() # Important: copy the dictionary
        recommended["explanation"] += f" {yellow}(Used first suggestion as fallback){reset}"

    # --- Final Checks ---
    # Did we manage to find anything useful at all?
    if not suggestions and not recommended["command"]:
         # If we found nothing, create an error message including the raw AI text
         error_message = (f"{yellow}Oops! Could not understand the AI's response format.{reset}\n"
                          f"{cyan}Here's what the AI said:{reset}\n---\n{ai_text}\n---")
         return None, None, error_message # Return nothing useful, plus the error

    # If recommendation wasn't found explicitly
    if not recommended["command"]:
        recommended["command"] = "Not Found"
        recommended["explanation"] = "Could not find the 'Recommended:' part in the AI answer."

    # If everything seemed okay (or we used Plan B), return the findings
    return suggestions, recommended, None # Return lists/dicts and no error message

# --- 8. The Main Part of the Script ---
# This special 'if' statement checks: "Are we running THIS file directly?"
# If yes, the code inside runs. If this file was just imported by another
# script, this part is skipped. This is the standard starting point.
if __name__ == "__main__":

    # --- Step A: Get the User's Task ---
    # 'sys.argv' is a list containing words typed on the command line when running the script.
    # sys.argv[0] is the script name itself (e.g., "command_suggester.py")
    # sys.argv[1] would be the first word *after* the script name.
    # We expect the task description to be passed right after the script name.
    if len(sys.argv) < 2: # Check if there's at least one word after the script name
        # If not, the user forgot to provide the task. Print help.
        print(f"{red}How to use this script:{reset}", file=sys.stderr)
        print(f"  python {os.path.basename(__file__)} \"Your task description here\" ", file=sys.stderr)
        print(f"{yellow}Example:{reset} python {os.path.basename(__file__)} \"find text files modified today\" ", file=sys.stderr)
        sys.exit(1) # Stop with an error

    # Join all words after the script name into a single task description string.
    # This handles tasks with spaces, like "find large files".
    user_task_description = " ".join(sys.argv[1:])

    # --- Step B: Get Ready to Talk to AI ---
    # Call our recipes (functions) to load the key and set up the AI model.
    # These functions will stop the script if they fail.
    api_key = load_api_key()
    model = configure_ai(api_key)

    # --- Step C: Ask the AI ---
    # Fill in the user's task into our prompt template
    prompt = suggester_prompt.replace("{USER_TASK}", user_task_description)
    # Print a status message (to stderr, so it doesn't get mixed with the final result)
    print(f"{blue}Asking the AI for ideas about: \"{user_task_description}\"...{reset}", file=sys.stderr)

    try: # We 'try' because the conversation with the AI might fail
        # Set up safety rules: block answers that seem harmful, hateful, etc.
        safety_settings = [
            {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
        ]
        # Send the completed prompt to the AI model and wait for the answer
        response = model.generate_content(prompt, safety_settings=safety_settings)

        # --- Check the AI's response carefully ---
        # (This part is a bit more complex, checking for safety blocks or empty answers)
        finish_reason = "OK" # Assume okay unless told otherwise
        block_reason_detail = ""
        ai_response_text = ""

        # Safely check the 'response' object for details (it might be structured differently sometimes)
        try:
             if response.candidates:
                 candidate = response.candidates[0]
                 # Why did the AI finish? (e.g., normally, safety block, error)
                 finish_reason = getattr(candidate, 'finish_reason', 'Unknown')
                 # Did safety rules block it?
                 if finish_reason == 3: # 3 often means safety block
                    block_reason_detail = "Blocked by AI safety filter."
                    # Try to get more specific block details if available
                    if hasattr(candidate, 'safety_ratings'):
                         blocked_ratings = [f"{r.category.name}" for r in candidate.safety_ratings if getattr(r,'blocked', False)]
                         if blocked_ratings: block_reason_detail += f" Categories: {', '.join(blocked_ratings)}"

             # Get the actual text answer, if it exists
             ai_response_text = getattr(response, 'text', None)

        except Exception as check_err:
            # If checking the response details causes an error, just note it.
             print(f"{yellow}Note: Couldn't fully check AI response details: {check_err}{reset}", file=sys.stderr)

        # Now, act based on the checks:
        if finish_reason == 3: # If blocked by safety
            print(f"{red}Sorry, the AI cannot provide suggestions for this task due to safety reasons.{reset}", file=sys.stderr)
            print(f"{yellow}Reason: {block_reason_detail}. Try asking differently.{reset}", file=sys.stderr)
            sys.exit(1) # Stop with error

        if not ai_response_text or not ai_response_text.strip(): # If no text answer
            print(f"{red}The AI gave an empty answer (Maybe finish reason was: {finish_reason}). Cannot show suggestions.{reset}", file=sys.stderr)
            sys.exit(1) # Stop with error

        # If we passed the checks, clean up the text
        ai_response_text = ai_response_text.strip()

    except Exception as e: # Catch other potential network/API errors during the chat
        print(f"{red}Something went wrong while talking to the AI: {e}{reset}", file=sys.stderr)
        sys.exit(1) # Stop with error

    # --- Step D: Understand the AI's Answer ---
    # Call our 'parse_suggestions' recipe to decode the AI's text
    suggestions, recommended, parse_error_msg = parse_suggestions(ai_response_text)

    # --- Step E: Show the Results to the User ---
    # Print everything below to 'stdout' (standard output), which is the default for print().
    # This allows the main Ai-CMD-X script to "catch" this output.

    print(f"{gold}--- AI Command Suggestions for '{user_task_description}' ---{reset}")

    if parse_error_msg:
        # If our parsing recipe reported an error, print that message
        print(parse_error_msg)
    else:
        # --- Show the suggestions ---
        if suggestions:
            print(f"\n{cyan}Suggested Commands:{reset}")
            # Loop through each suggestion found
            for sug in suggestions:
                print(f" {sug['number']}. {gold}{sug['command']}{reset}") # Print the command
                print(f"    {blue}Explanation:{reset} {sug['explanation']}") # Print its explanation
        else:
            print(f"{yellow}No specific suggestions were found in the AI's answer.{reset}")

        # --- Show the recommendation ---
        print(f"\n{cyan}Most Recommended:{reset}")
        # Check if we found a valid recommended command
        if recommended and recommended["command"] and recommended["command"] != "Not Found":
             print(f" {green}➡️ {gold}{recommended['command']}{reset}") # Print recommended command
             print(f"    {blue}Explanation:{reset} {recommended['explanation']}") # Print its explanation
        else:
             print(f"{yellow}Could not figure out the recommended command from the AI's answer.{reset}")

    # Print a closing line
    print(f"{gold}-----------------------------------------------------{reset}")

    # If the script reaches this point without stopping early (sys.exit),
    # it means everything worked, and it exits automatically with success (code 0).
