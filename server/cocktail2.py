import httpx
import json
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("cocktail_db")

# Base URL for the CocktailDB API (using test key '1')
COCKTAILDB_API_BASE = "https://www.thecocktaildb.com/api/json/v1/1"

# --- Helper Function for API Calls ---

async def make_cocktaildb_request(url: str) -> Optional[Dict[str, Any]]:
    """Makes a request to the CocktailDB API and returns the JSON response."""
    async with httpx.AsyncClient() as client:
        try:
            # Add a timeout to prevent hanging indefinitely
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            data = response.json()
            # The API sometimes returns empty strings or null instead of empty lists/objects
            if data and (data.get("drinks") is not None or data.get("ingredients") is not None):
                 return data
            else:
                 return None # Indicate no data found or unexpected format
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
            return None
        except json.JSONDecodeError:
            print(f"Failed to decode JSON response from {url}")
            return None
        except Exception as exc:
             print(f"An unexpected error occurred: {exc}")
             return None

# --- Formatting Helper (Optional but Recommended) ---
# You might want helper functions to format the JSON responses into more readable strings,
# similar to the format_alert function in the weather example[cite: 27].
# For brevity, these tools will return the raw JSON structure (or an error message).
# In a real application, formatting this output would be highly recommended.

def format_cocktail_list(data: Optional[Dict[str, Any]], result_key: str = "drinks") -> str:
    """Formats a list of cocktails or ingredients into a readable string."""
    if not data or not data.get(result_key):
        return f"No {result_key} found."

    items = data[result_key]
    formatted_items = []
    for item in items:
        # Simple formatting - adjust based on expected fields
        name = item.get('strDrink') or item.get('strIngredient') or 'Unknown Name'
        item_id = item.get('idDrink') or item.get('idIngredient') or 'N/A'
        details = f"Name: {name}, ID: {item_id}"
        # Add more details if needed, checking for None
        if 'strInstructions' in item:
             details += f"\n  Instructions: {item['strInstructions'][:100]}..." # Truncate long text
        if 'strGlass' in item:
             details += f"\n  Glass: {item['strGlass']}"
        if 'strAlcoholic' in item:
             details += f"\n  Type: {item['strAlcoholic']}"

        formatted_items.append(details)

    return "\n---\n".join(formatted_items) if formatted_items else f"No {result_key} found."

def format_single_cocktail(data: Optional[Dict[str, Any]]) -> str:
     """Formats details of a single cocktail."""
     return format_cocktail_list(data) # Reuse list formatter for single item


# --- Tool Implementations ---

@mcp.tool()
async def search_cocktail_by_name(name: str) -> str:
    """
    Searches for cocktails by their name.

    Args:
        name: The name of the cocktail to search for (e.g., margarita).
    """
    url = f"{COCKTAILDB_API_BASE}/search.php?s={name}"
    data = await make_cocktaildb_request(url)
    return format_cocktail_list(data, "drinks")


@mcp.tool()
async def list_cocktails_by_first_letter(letter: str) -> str:
    """
    Lists all cocktails starting with a specific letter.

    Args:
        letter: The first letter of the cocktails to list (e.g., a).
    """
    if len(letter) != 1 or not letter.isalpha():
        return "Please provide a single letter."
    url = f"{COCKTAILDB_API_BASE}/search.php?f={letter}"
    data = await make_cocktaildb_request(url)
    return format_cocktail_list(data, "drinks")


@mcp.tool()
async def search_ingredient_by_name(name: str) -> str:
    """
    Searches for ingredients by name. Provides basic details if found.

    Args:
        name: The name of the ingredient to search for (e.g., vodka).
    """
    url = f"{COCKTAILDB_API_BASE}/search.php?i={name}"
    data = await make_cocktaildb_request(url)
    # The ingredient search endpoint returns 'ingredients' key
    if not data or not data.get("ingredients"):
        return "No ingredient found or API error."

    ingredient = data["ingredients"][0] # Typically returns one main ingredient
    desc = ingredient.get('strDescription', 'No description available.')
    return (
        f"Ingredient: {ingredient.get('strIngredient', 'Unknown')}\n"
        f"ID: {ingredient.get('idIngredient', 'N/A')}\n"
        f"Type: {ingredient.get('strType', 'N/A')}\n"
        f"Alcoholic: {ingredient.get('strAlcohol', 'N/A')}\n"
        f"Description: {desc[:200] + '...' if desc and len(desc) > 200 else desc}" # Truncate long description
     )


@mcp.tool()
async def get_random_cocktail() -> str:
    """
    Looks up and returns the details of a single random cocktail.
    Note: The free API provides one random cocktail. Premium needed for multiple.
    """
    url = f"{COCKTAILDB_API_BASE}/random.php"
    data = await make_cocktaildb_request(url)
    return format_single_cocktail(data)


@mcp.tool()
async def lookup_cocktail_by_id(cocktail_id: str) -> str:
    """
    Looks up the full details of a specific cocktail by its ID.

    Args:
        cocktail_id: The unique ID of the cocktail (e.g., 11007).
    """
    if not cocktail_id.isdigit():
        return "Please provide a valid numeric cocktail ID."
    url = f"{COCKTAILDB_API_BASE}/lookup.php?i={cocktail_id}"
    data = await make_cocktaildb_request(url)
    return format_single_cocktail(data)


# --- Running the Server ---

if __name__ == "__main__":
    # Run the server using stdio transport as shown in the guide [cite: 32]
    mcp.run(transport='stdio')