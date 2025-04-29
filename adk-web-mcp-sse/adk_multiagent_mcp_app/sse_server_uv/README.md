# Set Up MCP server using Cloud Run

## Setup and Deployment



In your Cloud Shell or local terminal (with gcloud CLI configured), set the following environment variables:

Note: The below parameters need to match with the values in .env file.

```bash
# Define a name for your Cloud Run service
export SERVICE_NAME='weather-mcp-server2'

# Specify the Google Cloud region for deployment (ensure it supports required services)
export LOCATION='us-central1'

# Replace with your Google Cloud Project ID
export PROJECT_ID='dw-genai-dev'
```

In Cloud Shell, execute the following command:


```bash
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $LOCATION \
  --project $PROJECT_ID \
  --memory 4G \
  --allow-unauthenticated \
  --port 8000

```

