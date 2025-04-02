from google.cloud import secretmanager
import requests
import black
import os
import re
import json
from typing import Union, Dict, List, Optional 

def access_secret_version(project_id, secret_id, version_id="latest"):
    """
    Access the payload for the given secret version if one exists. The version
    can be a version number as a string (e.g. "5") or an alias (e.g. "latest").
    """

    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version.
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    # Access the secret version.
    response = client.access_secret_version(request={"name": name})

    # Return the decoded payload.
    return response.payload.data.decode("UTF-8")


def get_url_content(url):
    try:
        # Send an HTTP GET request to the URL
        response = requests.get(url)

        # Raise an exception if the request returned an error status code (like 404 or 500)
        response.raise_for_status()

        # Get the content of the response as text (HTML, in this case)
        # 'requests' automatically decodes the content based on HTTP headers
        file_content = response.text

        # Now you can work with the content
        print("Successfully fetched content")
        return file_content
        # Or, save it to a file:
        # with open("server_page.html", "w", encoding="utf-8") as f:
        #     f.write(file_content)
        # print("Content saved to server_page.html")

    except requests.exceptions.RequestException as e:
        # Handle potential errors during the request (e.g., network issues, DNS errors)
        print(f"Error fetching URL {url}: {e}")
    except requests.exceptions.HTTPError as e:
        # Handle HTTP error responses (e.g., 404 Not Found, 503 Service Unavailable)
        print(f"HTTP Error for {url}: {e}")


def format_python(raw_code, output_filename):

    try:
        # Format the code string using black
        # Use default FileMode which is generally recommended
        formatted_code = black.format_str(raw_code, mode=black.FileMode())

        # Save the formatted code to the specified file
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(formatted_code)

        print(f"Successfully formatted the code and saved it to '{output_filename}'")

    except black.InvalidInput as e:
        print(
            f"Error formatting code: The input string does not seem to be valid Python syntax."
        )
        print(f"Details: {e}")
    except Exception as e:
        print(f"An error occurred while writing the file: {e}")


def extract_json_from_string(input_str: str) -> Optional[Union[Dict, List]]:
    """
    Extracts JSON data from a string, handling potential variations.

    This function attempts to find JSON data within a string. It specifically
    looks for JSON enclosed in Markdown-like code fences (```json ... ```).
    If such a block is found, it extracts and parses the content.
    If no code block is found, it attempts to parse the entire input string
    as JSON.

    Args:
        input_str: The string potentially containing JSON data. It might be
                   a plain JSON string or contain a Markdown code block
                   with JSON, possibly preceded by other text (like 'shame').

    Returns:
        The parsed JSON object (typically a dictionary or list) if valid
        JSON is found and successfully parsed.
        Returns None if no valid JSON is found, if parsing fails, or if the
        input is not a string.
    """
    if not isinstance(input_str, str):
        # Handle cases where input is not a string
        return None

    # Pattern to find JSON within ```json ... ``` blocks
    # - ````json`: Matches the start fence.
    # - `\s*`: Matches any leading whitespace after the fence marker.
    # - `(.*?)`: Captures the content (non-greedily) between the fences. This is group 1.
    # - `\s*`: Matches any trailing whitespace before the end fence.
    # - ` ``` `: Matches the end fence.
    # - `re.DOTALL`: Allows '.' to match newline characters.
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, input_str, re.DOTALL)

    json_string_to_parse = None

    if match:
        # If a markdown block is found, extract its content
        json_string_to_parse = match.group(1).strip() # Get captured group and remove surrounding whitespace
    else:
        # If no markdown block, assume the *entire* input might be JSON
        # We strip whitespace in case the string is just JSON with padding
        json_string_to_parse = input_str.strip()

    if not json_string_to_parse:
        # If after stripping, the potential JSON string is empty, return None
        return None

    try:
        # Attempt to parse the determined string (either from block or whole input)
        parsed_json = json.loads(json_string_to_parse)
        return parsed_json
    except json.JSONDecodeError:
        # Parsing failed, indicating the string wasn't valid JSON
        return None
    except Exception as e:
        # Catch other potential unexpected errors during parsing
        print(f"An unexpected error occurred during JSON parsing: {e}")
        return None