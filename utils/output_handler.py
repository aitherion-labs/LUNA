import os
from datetime import datetime


def save_to_temp_file(chat_id: str, input: str, response: str):
    """
    Saves the interaction to a separate .txt file for each chat_id
    inside the /tmp directory.
    """
    temp_dir = "tmp"

    # Sanitize the chat_id to create a safe filename
    safe_chat_id = "".join(
        c for c in chat_id if c.isalnum() or c in ("-", "_")
    ).rstrip()
    if not safe_chat_id:
        safe_chat_id = "invalid_chat_id"

    # Create a filename based on the chat_id
    log_file_path = os.path.join(temp_dir, f"{safe_chat_id}.txt")

    # Ensure the /tmp directory exists
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Get the current timestamp
    timestamp = datetime.now().isoformat()

    # Log entry updated to use 'Chat ID'
    log_entry = f"""
---
Timestamp: {timestamp}
Chat ID: {chat_id}
Input: {input}
Response: {response}
"""

    try:
        # Open the file in "append" mode
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

        print(f"Interaction successfully saved to: {log_file_path}")
        return log_file_path

    except Exception as e:
        print(f"Error saving log file: {e}")
        return None
