## An ADK Agent integrated with MCP Client

This web application was developed using Google's ADK (Agent Development Kit) and MCP (Model Context Protocol). Specifically, the Agent relies on the Google ADK. A local MCP server instance, established using custom server code designed for cocktail data management, facilitates data retrieval. The web application acts as an MCP client to fetch cocktail information via this local server.

Screenshot:

<img src="../asset/adk_app.png" alt="Descriptive alt text" width="700" />

Project Structure

```bash
your_project_folder/  # Project folder
|── adk_mcp_app
    ├── main.py
    ├── .env
    ├── mcp_server
    │   └── cocktail.py
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    └── static
        └── index.html
```

### Run the app

Start the Fast API: Run the following command within the `adk_mcp_app` folder

1. Set up values in `.env` file

Create a .env file with the following contents:

```bash
# Choose Model Backend: 0 -> ML Dev, 1 -> Vertex
GOOGLE_GENAI_USE_VERTEXAI=1

# ML Dev backend config
GOOGLE_API_KEY=YOUR_VALUE_HERE

# Vertex backend config
GOOGLE_CLOUD_PROJECT="<your project id>"
GOOGLE_CLOUD_LOCATION="us-central1"
```

If using Google API key:

```bash
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=YOUR_VALUE_HERE
```

If using Vertex AI Project ID:

```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=YOUR_VALUE_HERE
GOOGLE_CLOUD_LOCATION="us-central1"
```

2. Run the below command

```bash
uv run uvicorn main:app --reload --port 8002
```

The example shows you can chat with the app to get cocktail details from the cocktail db website via a local MCP server.
