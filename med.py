import httpx
import xml.etree.ElementTree as ET
import re
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(name="medlineplus", version="1.0.0")

# Constants
MEDLINEPLUS_API_BASE = "https://wsearch.nlm.nih.gov/ws/query"


# Helper function to strip HTML tags
def strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)


async def make_medlineplus_request(term: str) -> Optional[ET.Element]:
    """Make a request to the MedlinePlus API and parse the XML response."""
    params = {
        "db": "healthTopics",
        "term": term,
        "retmax": 1,  # Get only the top result
        "rettype": "brief",  # Get summary/snippet
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                MEDLINEPLUS_API_BASE, params=params, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            # Ensure the response is parsed correctly, handling potential encoding issues
            xml_content = response.content
            # Attempt to parse XML
            try:
                root = ET.fromstring(xml_content)
                return root
            except ET.ParseError as e:
                print(f"XML Parse Error: {e}")
                return None
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except httpx.RequestError as e:
        print(f"Request error occurred: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


@mcp.tool()
async def get_medical_term(term: str) -> str:
    """Get an explanation for a medical term from MedlinePlus.

    Args:
        term: The medical term to look up.
    """
    root = await make_medlineplus_request(term)

    if root is None:
        return "Error: Could not fetch or parse data from MedlinePlus API."

    doc_list = root.find("list")
    if doc_list is None or len(doc_list) == 0:
        return f"No information found for the term '{term}' on MedlinePlus."

    document = doc_list.find("document")
    if document is None:
        return f"No specific document found for the term '{term}' on MedlinePlus."

    title = "Not Available"
    explanation = "Not Available"

    # Extract title and summary/snippet
    for content in document.findall("content"):
        name = content.get("name")
        text = content.text or ""
        if name == "title":
            title = strip_html(text)
        elif name == "FullSummary":  # Prioritize FullSummary
            explanation = strip_html(text)
        elif (
            name == "snippet" and explanation == "Not Available"
        ):  # Fallback to snippet
            explanation = strip_html(text)

    if explanation == "Not Available":
        return (
            f"Found topic '{title}', but no summary or snippet available for '{term}'."
        )

    return f"Term: {title}\n\nExplanation:\n{explanation.strip()}"


if __name__ == "__main__":
    # Initialize and run the server using stdio transport
    mcp.run(transport="stdio")
