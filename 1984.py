import requests
import argparse
import json
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ANSI escape codes for colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

# Argparse configs
parser = argparse.ArgumentParser()
parser.add_argument("-u", type=str, help="Target URL")
parser.add_argument("-l", type=str, help="List of URLs")
parser.add_argument("-t", type=str, help="Target technology")
parser.add_argument("-e", type=str, help="Error log")
args = parser.parse_args()

URL = args.u
url_list = args.l
errolog = args.e
urls = []
if not URL and not url_list:
    print(f"{RED}Specify at least a URL or a URL list!{RESET}")
    exit(1)

if url_list:
    try:
        with open(url_list, 'r') as file:
            urls = file.readlines()
    except FileNotFoundError:
        print(f"{RED}File name or directory doesn't exist!{RESET}")
        exit(1)

# Load phrases from js.json and nice_words.json
try:
    with open('wordlists/js.json', 'r') as file:
        js_phrases = json.load(file)['js']
except FileNotFoundError:
    print(f"{RED}JS file not found!{RESET}")
    exit(1)

try:
    with open('wordlists/nice_words.json', 'r') as file:
        nice_phrases = json.load(file)['words']
except FileNotFoundError:
    print(f"{RED}Nice words file not found!{RESET}")
    exit(1)

# Combine phrases from both files
all_phrases = js_phrases + nice_phrases

# Set up Chrome options and capabilities
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--log-level=3")  # Suppress logs

# Enable logging of network traffic
capabilities = {
    'goog:loggingPrefs': {'performance': 'ALL'},
}
chrome_options.set_capability("goog:loggingPrefs", capabilities['goog:loggingPrefs'])

# Set up WebDriver (ensure chromedriver is in your PATH)
driver = webdriver.Chrome(options=chrome_options)

# Compile the regular expression pattern to match the unwanted extensions and scripts
pattern = re.compile(r'\.(' + '|'.join([
    'css', 'jpg', 'jpeg', 'png', 'svg', 'img', 'gif', 'exe', 'mp4', 'flv', 'pdf', 'doc',
    'ogv', 'webm', 'wmv', 'webp', 'mov', 'mp3', 'm4a', 'm4p', 'ppt', 'pptx', 'scss', 'tif',
    'tiff', 'ttf', 'fit', 'otf', 'woff', 'woff2', 'bmp', 'ico', 'eot', 'htc', 'swf', 'rtf',
    'image', 'rf'
]) + r')$|jquery.*\.js$|gtm.*\.js$|analytics\.js$|gtag\.js$|googletagmanager\.js$|adsbygoogle\.js$|fbevents\.js$|widgets\.js$|iframe_api$|player\.js$|maps\.googleapis\.com$|intercom$|cdnjs\.com$|maxcdn\.com$|bootstrap.*\.js$', re.IGNORECASE)

# Add single URL to the list if provided
if URL:
    urls.append(URL)

if urls:
    for url in urls:
        url = url.strip()
        try:
            driver.get(url)
            time.sleep(5)  # Wait for a few seconds to let the network requests load

            # Capture and analyze network requests
            logs = driver.get_log('performance')
            api_endpoints = set()
            for entry in logs:
                try:
                    log = json.loads(entry['message'])['message']
                    if 'Network.requestWillBeSent' in log['method']:
                        if 'params' in log and 'request' in log['params']:
                            request_url = log['params']['request'].get('url')
                            if request_url and not pattern.search(request_url):
                                api_endpoints.add(request_url)
                        else:
                            if errolog:
                                print(f"{RED}KeyError: Missing 'params' or 'request' in log: {log}{RESET}")
                except KeyError as e:
                    print(f"{RED}KeyError occurred: {e}{RESET}")
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"{RED}Error parsing log entry: {e}{RESET}")

            # Request and print responses from API endpoints
            print(f"Discovered API endpoints for {url}:")

            for endpoint in api_endpoints:
                try:
                    api_response = requests.get(endpoint)
                    raw_data = f"{api_response.headers}\n{api_response.content.decode('utf-8', errors='replace')}".lower()  # Convert content to lower case
                    found_phrases = [phrase for phrase in all_phrases if phrase.lower() in raw_data]  # Convert phrases to lower case
                    if found_phrases:
                        print(f"Endpoint: {endpoint}\n{GREEN}Found Phrases: {found_phrases}{RESET}\n")
                except requests.exceptions.RequestException as e:
                    print(f"{RED}An error occurred while requesting endpoint {endpoint}: {e}{RESET}")

            # Process response data for the main URL
            req = requests.get(url)
            raw_data = f"{req.headers}\n{req.content.decode('utf-8', errors='replace')}".lower()  # Convert content to lower case
            found_phrases = [phrase for phrase in all_phrases if phrase.lower() in raw_data]  # Convert phrases to lower case
            if found_phrases:
                print(f"Main URL Response for {url}:\n{GREEN}Found Phrases: {found_phrases}{RESET}")
            else:
                print(f"{RED}No data received for {url}.{RESET}")
        except requests.exceptions.RequestException as e:
            print(f"{RED}An error occurred with URL {url}: {e}{RESET}")
        except Exception as e:
            print(f"{RED}An error occurred while processing {url}: {e}{RESET}")

# Close the WebDriver
driver.quit()
