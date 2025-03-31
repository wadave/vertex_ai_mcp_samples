import httpx
import xml.etree.ElementTree as ET
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    server_name="medlineplus",
    description="Provides access to MedlinePlus health information.",
    version="1.0.0",
)

# Constants
MEDLINE_API_BASE = "https://wsearch.nlm.nih.gov/ws/query"
USER_AGENT = "mcp-medlineplus-tool/1.0"


async def make_medline_request(term: str) -> Optional[ET.Element]:
    """Make a request to the MedlinePlus Web Service and parse the XML response."""
    params = {
        "db": "healthTopics",
        "term": term,
        "rettype": "brief",  # Get summary and snippet
        "retmax": 1,  # Get only the top result
    }
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                MEDLINE_API_BASE, params=params, headers=headers, timeout=30.0
            )
            response.raise_for_status()
            # Ensure content is not empty before parsing
            if not response.content:
                print("Received empty response from MedlinePlus API")
                return None
            # Parse XML response
            root = ET.fromstring(response.content)
            return root
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
            return None
        except ET.ParseError as e:
            print(f"XML parsing error: {e}")
            print(
                f"Response content: {response.text[:500]}..."
            )  # Log partial content for debugging
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None


@mcp.tool()
async def get_medical_term(medical_term: str) -> str:
    """Get an explanation for a given medical term from MedlinePlus.

    Args:
        medical_term: The medical term to look up (e.g., 'diabetes', 'asthma').
    """
    root = await make_medline_request(medical_term)

    if root is None:
        return (
            f"Could not retrieve information for '{medical_term}' due to an API error."
        )

    try:
        # Find the list of documents
        doc_list = root.find("list")
        if doc_list is None or not len(doc_list):
            # Check for spelling correction suggestion
            spelling_correction = root.find("spellingCorrection")
            if spelling_correction is not None and spelling_correction.text:
                return f"No direct match found for '{medical_term}'. Did you mean '{spelling_correction.text}'?"
            return f"No information found for '{medical_term}'."

        # Get the first document
        first_doc = doc_list.find("document")
        if first_doc is None:
            return f"No documents found in the response for '{medical_term}'."

        # Extract title, summary, and snippet
        title = ""
        summary = ""
        snippet = ""
        url = first_doc.get("url", "N/A")

        for content in first_doc.findall("content"):
            name = content.get("name")
            text_content = "".join(
                content.itertext()
            ).strip()  # Extract text, handling potential subtags like <span class="qt0">
            if name == "title":
                title = text_content
            elif name == "FullSummary":
                summary = text_content
            elif name == "snippet":
                snippet = text_content

        if summary:
            return f"Term: {title}\nURL: {url}\n\nSummary:\n{summary}"
        elif snippet:
            # Clean up snippet if necessary (remove '...' etc.)
            cleaned_snippet = snippet.replace("...", "").strip()
            return f"Term: {title}\nURL: {url}\n\nSnippet:\n{cleaned_snippet}"
        elif title:
            return f"Term: {title}\nURL: {url}\n\nNo summary or snippet available for this term."
        else:
            return f"Found a related page for '{medical_term}' but could not extract title or summary. URL: {url}"

    except Exception as e:
        print(f"Error processing MedlinePlus response: {e}")
        return f"Error processing the information for '{medical_term}'."


if __name__ == "__main__":
    mcp.run(transport="stdio")
