from typing import Any, Dict, List, Optional
import httpx
import json
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("cocktail_db")

# Constants
API_BASE_URL = "https://www.thecocktaildb.com/api/json/v1/1"
USER_AGENT = "mcp-cocktaildb-server/1.0"


async def make_api_request(
    endpoint: str, params: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """Makes a request to TheCocktailDB API."""
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, params=params, headers=headers, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()
            # The API sometimes returns an empty string or null instead of proper empty results
            if isinstance(data, str) and not data.strip():
                return None
            if data is None:
                return None
            return data
    except httpx.RequestError as e:
        print(f"HTTP Request failed: {e}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"HTTP Status error: {e.response.status_code} - {e.request.url}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON response: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def format_cocktail_details(drink: Dict[str, Any]) -> str:
    """Formats full cocktail details into a readable string."""
    details = []
    details.append(f"Name: {drink.get('strDrink', 'N/A')}")
    details.append(f"ID: {drink.get('idDrink', 'N/A')}")
    if drink.get("strCategory"):
        details.append(f"Category: {drink['strCategory']}")
    if drink.get("strAlcoholic"):
        details.append(f"Type: {drink['strAlcoholic']}")
    if drink.get("strGlass"):
        details.append(f"Glass: {drink['strGlass']}")
    if drink.get("strInstructions"):
        details.append(f"Instructions: {drink['strInstructions']}")

    ingredients = []
    for i in range(1, 16):
        ingredient = drink.get(f"strIngredient{i}")
        measure = drink.get(f"strMeasure{i}")
        if ingredient:
            ingredients.append(
                f"- {measure.strip() if measure else ''} {ingredient.strip()}".strip()
            )

    if ingredients:
        details.append("Ingredients:")
        details.extend(ingredients)

    if drink.get("strDrinkThumb"):
        details.append(f"Thumbnail: {drink['strDrinkThumb']}")

    return "\n".join(details)


def format_ingredient_details(ingredient: Dict[str, Any]) -> str:
    """Formats ingredient details into a readable string."""
    details = []
    details.append(f"Name: {ingredient.get('strIngredient', 'N/A')}")
    details.append(f"ID: {ingredient.get('idIngredient', 'N/A')}")
    if ingredient.get("strDescription"):
        details.append(f"Description: {ingredient['strDescription']}")
    if ingredient.get("strType"):
        details.append(f"Type: {ingredient['strType']}")
    if ingredient.get("strAlcohol"):
        details.append(f"Alcoholic: {ingredient['strAlcohol']}")
    if ingredient.get("strABV"):
        details.append(f"ABV: {ingredient['strABV']}%")
    return "\n".join(details)


@mcp.tool()
async def search_cocktail_by_name(name: str) -> str:
    """Search for cocktails by their name.

    Args:
        name: The name of the cocktail to search for (e.g., Margarita).
    """
    data = await make_api_request("search.php", params={"s": name})
    if not data or not data.get("drinks"):
        return f"No cocktails found matching the name '{name}'."

    drinks = data["drinks"]
    response_lines = [f"Found {len(drinks)} cocktail(s) matching '{name}':"]
    for drink in drinks:
        response_lines.append(
            f"- {drink.get('strDrink', 'Unknown Name')} (ID: {drink.get('idDrink', 'N/A')})"
        )
        response_lines.append(
            f"  Instructions: {drink.get('strInstructions', 'N/A')[:100]}..."
        )  # Summary
        response_lines.append("---")

    return "\n".join(response_lines)


@mcp.tool()
async def list_cocktails_by_first_letter(letter: str) -> str:
    """List all cocktails starting with a specific letter.

    Args:
        letter: The first letter to filter cocktails by (must be a single character).
    """
    if len(letter) != 1 or not letter.isalpha():
        return "Invalid input: Please provide a single letter."

    data = await make_api_request("search.php", params={"f": letter})
    if not data or not data.get("drinks"):
        return f"No cocktails found starting with the letter '{letter}'."

    drinks = data["drinks"]
    response_lines = [f"Found {len(drinks)} cocktail(s) starting with '{letter}':"]
    for drink in drinks:
        response_lines.append(
            f"- {drink.get('strDrink', 'Unknown Name')} (ID: {drink.get('idDrink', 'N/A')})"
        )
    return "\n".join(response_lines)


@mcp.tool()
async def search_ingredient_by_name(ingredient_name: str) -> str:
    """Search for an ingredient by its name.

    Args:
        ingredient_name: The name of the ingredient to search for (e.g., Vodka).
    """
    data = await make_api_request("search.php", params={"i": ingredient_name})
    if not data or not data.get("ingredients"):
        return f"No ingredient found matching the name '{ingredient_name}'."

    # API returns a list, but usually search by name yields one result
    ingredient = data["ingredients"][0]
    return format_ingredient_details(ingredient)


@mcp.tool()
async def list_random_cocktails() -> str:
    """Get a single random cocktail recipe."""
    data = await make_api_request("random.php")
    if not data or not data.get("drinks"):
        return "Could not fetch a random cocktail."

    drink = data["drinks"][0]
    return format_cocktail_details(drink)


@mcp.tool()
async def lookup_cocktail_details_by_id(cocktail_id: str) -> str:
    """Look up the full details of a cocktail by its ID.

    Args:
        cocktail_id: The unique ID of the cocktail.
    """
    data = await make_api_request("lookup.php", params={"i": cocktail_id})
    if not data or not data.get("drinks"):
        return f"No cocktail found with ID '{cocktail_id}'."

    drink = data["drinks"][0]
    return format_cocktail_details(drink)


if __name__ == "__main__":
    mcp.run(transport="stdio")
