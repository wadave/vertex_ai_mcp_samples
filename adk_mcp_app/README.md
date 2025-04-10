## An ADK Agent integrated with MCP Client
This web application was developed using Google's ADK (Agent Development Kit) and MCP (Model Context Protocal). Specifically, the Agent relies on the Google ADK. A local MCP server instance, established using custom server code designed for cocktail data management, facilitates data retrieval. The web application acts as an MCP client to fetch cocktail information via this local server. 

### Create & Activate Virtual Environment (Recommended):

```
python -m venv .venv
source .venv/bin/activate
```
### Install ADK:

```
pip install google-adk fastapi
```
1. Project Structure
Create the following folder structure with empty files:

```
your_project_folder/  # Project folder
|── adk_mcp_app
    ├── main.py
    ├── .env
    ├── mcp_server
    │   └── cocktail.py
    ├── README.md
    └── static
        └── index.html
```
### Run the app
Start the Fast API: Run the following command to start CLI interface with `adk_mcp_app` folder
1. Set up vales in `.env ` file

Create a .env file with the following contents:
```
# Choose Model Backend: 0 -> ML Dev, 1 -> Vertex
GOOGLE_GENAI_USE_VERTEXAI=1

# ML Dev backend config
GOOGLE_API_KEY=YOUR_VALUE_HERE

# Vertex backend config
GOOGLE_CLOUD_PROJECT="<your project id>"
GOOGLE_CLOUD_LOCATION="us-central1"
```

If using Google API key:
```
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=YOUR_VALUE_HERE
```

If using Vertex AI Project ID:
```
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=YOUR_VALUE_HERE
GOOGLE_CLOUD_LOCATION="us-central1"
```

1.  Run the below command

```
uvicorn main:app --reload
```

