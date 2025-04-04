from typing import Any, Optional
import httpx
import xml.etree.ElementTree as ET
import urllib.parse
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(name="medlineplus", version="1.0.0")

# Constants
API_BASE_URL = "https://wsearch.nlm.nih.gov/ws/query"
USER_AGENT = (
    "mcp-medlineplus-server/1.0 (MCP Example; contact: info@modelcontextprotocol.io)"
)


async def make_api_request(term: str) -> Optional[str]:
    """Makes a request to the MedlinePlus API and returns the XML response as text."""
    encoded_term = urllib.parse.quote_plus(term)
    url = f"{API_BASE_URL}?db=healthTopics&term={encoded_term}&rettype=brief&retmax=1"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/xml"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text
    except httpx.RequestError as e:
        print(f"HTTP Request failed: {e}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"HTTP Status error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during API request: {e}")
        return None


def parse_medlineplus_response(xml_text: str) -> str:
    """Parses the XML response and extracts relevant information."""
    try:
        root = ET.fromstring(xml_text)

        # Check for spelling correction
        spelling_correction = root.findtext("spellingCorrection")
        if spelling_correction:
            return f"Did you mean '{spelling_correction}'? Please try searching again with the corrected term."

        # Check result count
        count_text = root.findtext("count")
        if count_text is None or int(count_text) == 0:
            return "No information found for that medical term."

        # Get the first document
        first_doc = root.find(".//list/document")
        if first_doc is None:
            return "Could not find the result document in the response."

        title = "Not Available"
        snippet = "Not Available"

        # Extract title and snippet
        for content in first_doc.findall("content"):
            if content.get("name") == "title":
                # Remove highlighting tags like <span class="qt0">...
                title_element = ET.fromstring(f"<root>{content.text}</root>")
                title = "".join(title_element.itertext()).strip()
            elif content.get("name") == "snippet":
                # Remove highlighting tags and clean up snippet
                snippet_element = ET.fromstring(f"<root>{content.text}</root>")
                snippet_parts = [
                    part.strip()
                    for part in snippet_element.itertext()
                    if part and part.strip()
                ]
                snippet = " ".join(snippet_parts).strip()

        if title == "Not Available" and snippet == "Not Available":
            return "Found a result, but could not extract title or snippet."

        return f"Term: {title}\n\nExplanation: {snippet}"

    except ET.ParseError as e:
        print(f"Failed to parse XML: {e}")
        return "Error: Could not parse the response from the medical dictionary."
    except Exception as e:
        print(f"An unexpected error occurred during XML parsing: {e}")
        return "Error: An unexpected error occurred while processing the response."


@mcp.tool()
async def get_medical_term(term: str) -> str:
    """Get the explanation for a medical term from MedlinePlus.

    Args:
        term: The medical term to search for.
    """
    xml_response = await make_api_request(term)
    if xml_response is None:
        return "Error: Failed to retrieve data from the MedlinePlus service."

    explanation = parse_medlineplus_response(xml_response)
    return explanation


if __name__ == "__main__":
    # Run the server using standard I/O
    mcp.run(transport="stdio")
