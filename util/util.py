from google.cloud import secretmanager
import requests
import black
import os


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
