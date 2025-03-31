from typing import Any
import httpx
import xml.etree.ElementTree as ET
from mcp.server.fastmcp import FastMCP
import html

# Initialize FastMCP server
mcp = FastMCP("medlineplus")

# Constants
MEDLINEPLUS_API_BASE = "https://wsearch.nlm.nih.gov/ws/query"


async def make_api_request(url: str) -> str | None:
    """Helper function to make API requests to MedlinePlus."""
    # MedlinePlus requests a User-Agent
    headers = {
        "User-Agent": "MCP-Example-Client/1.0 (https://github.com/modelcontextprotocol/examples)"
    }
    try:
        async with httpx.AsyncClient() as client:
            print(f"Requesting URL: {url}")
            response = await client.get(
                url, headers=headers, timeout=30.0, follow_redirects=True
            )
            print(f"Received status code: {response.status_code}")
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}")
        # Provide more specific error messages based on status code if needed
        if e.response.status_code == 404:
            return "Error: The requested resource was not found."
        else:
            return f"Error: Received status code {e.response.status_code} from MedlinePlus API."
    except httpx.RequestError as e:
        print(f"Request error occurred: {e}")
        return "Error: Could not connect to MedlinePlus API."
    except Exception as e:
        print(f"An unexpected error occurred during request: {e}")
        return "Error: An unexpected error occurred while fetching data."


def parse_summary_from_xml(xml_string: str) -> str | None:
    """Parse the FullSummary from the MedlinePlus XML response."""
    try:
        # Clean potential control characters before parsing
        # xml_string = ''.join(c for c in xml_string if ET.XMLParser._is_legal_char(ord(c)))
        root = ET.fromstring(xml_string)
        list_element = root.find("list")

        if list_element is None or not list(list_element):
            # Check for spelling corrections or explicit no results
            spelling_correction = root.find("spellingCorrection")
            if spelling_correction is not None and spelling_correction.text:
                return f"Did you mean '{spelling_correction.text}'? Please try again with the corrected term."
            count = root.find("count")
            if count is not None and count.text == "0":
                return "No results found for this term."
            # General inability to find results
            return "Could not find any results in the API response."

        # Get the first document, assuming it's the most relevant
        first_document = list_element.find("document")
        if first_document is None:
            return "No documents found in the result list."

        # Find the FullSummary content element
        summary_element = None
        for content in first_document.findall("content"):
            if content.get("name") == "FullSummary":
                summary_element = content
                break

        if summary_element is not None:
            # Reconstruct text content including children (HTML tags), then unescape HTML entities
            summary_text = html.unescape("".join(summary_element.itertext()).strip())
            # Basic cleanup of potential excessive whitespace
            summary_text = " ".join(summary_text.split())
            return (
                summary_text
                if summary_text
                else "Summary field was empty for this term."
            )
        else:
            # Fallback if FullSummary is missing
            snippet_element = None
            for content in first_document.findall("content"):
                if content.get("name") == "snippet":
                    snippet_element = content
                    break
            if snippet_element is not None:
                snippet_text = html.unescape(
                    "".join(snippet_element.itertext()).strip()
                )
                snippet_text = " ".join(snippet_text.split())
                if snippet_text:
                    return f"Full summary not available. Snippet: {snippet_text}"

            return "Summary information not available for this term."

    except ET.ParseError as e:
        print(f"Error parsing XML response: {e}")
        # Log part of the problematic XML for debugging if possible and safe
        # print(f"Problematic XML (first 500 chars): {xml_string[:500]}")
        return "Error: Could not parse the response from MedlinePlus API. It might be malformed."
    except Exception as e:
        print(f"Error during XML parsing: {e}")
        return "Error: An error occurred while processing the API response."


@mcp.tool()
async def get_medical_term(term: str) -> str:
    """
    Get an explanation for a medical term from MedlinePlus.

    Args:
        term: The medical term to search for (e.g., 'diabetes', 'asthma').
    """
    print(f"Received request for term: {term}")
    # Use rettype=brief (default) and retmax=1 to get the most relevant summary
    # URL encode the term properly using httpx's capabilities
    params = {"db": "healthTopics", "term": term, "retmax": "1"}

    # Construct URL with httpx for proper encoding
    request = httpx.Request("GET", MEDLINEPLUS_API_BASE, params=params)
    url = str(request.url)

    xml_response = await make_api_request(url)

    if xml_response is None:
        return "Error: Failed to get a response from MedlinePlus API."
    if xml_response.startswith("Error:"):
        return xml_response

    summary = parse_summary_from_xml(xml_response)

    if summary is None:
        return "Error: Could not extract summary from API response."
    elif summary.startswith("Error:"):
        return summary
    elif summary == "No results found for this term.":
        return f"MedlinePlus does not have specific information for the term '{term}'. Please try a broader or related term."
    elif summary == "Summary information not available for this term.":
        return f"Could not find a definition or summary for '{term}' on MedlinePlus."

    print(f"Returning summary for '{term}'")
    # Limit summary length if necessary, though usually desirable to return full summary
    # max_len = 1000
    # return summary[:max_len] + ('...' if len(summary) > max_len else '')
    return summary


if __name__ == "__main__":
    mcp.run(transport="stdio")
