import os
import sys
from typing import override, Dict, Any, List
import asyncio
from contextlib import asynccontextmanager

import click
import uvicorn 

from agent import WeatherAgent 
from agent_executor import WeatherAgentExecutor
from dotenv import load_dotenv

from a2a.server import A2AServer
from a2a.server.request_handlers import DefaultA2ARequestHandler
from a2a.types import (
    AgentAuthentication,
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(override=True)

SERVER_CONFIGS = {
    "weather": {
        "command": "python",
        "args": ["./weather_server.py"],
        "transport": "stdio",
    },
}

app_context: Dict[str, Any] = {}


@asynccontextmanager
async def app_lifespan(context: Dict[str, Any]):
    """Manages the lifecycle of shared resources like the MCP client and tools."""
    print("Lifespan: Initializing MCP client and tools...")

    mcp_client_manager = MultiServerMCPClient(SERVER_CONFIGS)
    active_client = None 
    try:
        active_client = await mcp_client_manager.__aenter__()
        context['mcp_client'] = active_client 
        context['mcp_tools'] = active_client.get_tools() 
        tool_count = len(context['mcp_tools']) if context['mcp_tools'] else 0
        print(f"Lifespan: MCP Tools preloaded successfully ({tool_count} tools found).")
        yield  # Application runs here
    except Exception as e:
        print(f"Lifespan: Error during initialization: {e}", file=sys.stderr)
        # Depending on the severity, you might want to re-raise or exit
        raise
    finally:
        print("Lifespan: Shutting down MCP client...")
        if active_client: # Check if the client was successfully activated
            try:
                await mcp_client_manager.__aexit__(None, None, None)
                print("Lifespan: MCP Client closed.")
            except Exception as e:
                print(f"Lifespan: Error during MCP client shutdown: {e}", file=sys.stderr)
        else:
            print("Lifespan: MCP Client was not activated, no shutdown needed for it via __aexit__.")
        context.clear()


@click.command()
@click.option('--host', 'host', default='localhost', help="Hostname to bind the server to.")
@click.option('--port', 'port', default=10001, type=int, help="Port to bind the server to.")
@click.option('--log-level', 'log_level', default='info', help="Uvicorn log level.")
def cli_main(host: str, port: int, log_level: str):
    """Command Line Interface to start the Weather Agent server."""
    if not os.getenv('GOOGLE_API_KEY'):
        print('GOOGLE_API_KEY environment variable not set.', file=sys.stderr)
        sys.exit(1)

    async def run_server_async():
        async with app_lifespan(app_context):
            if not app_context.get('mcp_tools'):
                print("Warning: MCP tools were not loaded. Agent may not function correctly.", file=sys.stderr)
                # Depending on requirements, you could sys.exit(1) here

            # Initialize WeatherAgentExecutor with preloaded tools
            weather_agent_executor = WeatherAgentExecutor(mcp_tools=app_context.get('mcp_tools', []))
            
            request_handler = DefaultA2ARequestHandler(
                agent_executor=weather_agent_executor
            )

            # Create the A2AServer instance
            a2a_server = A2AServer(
                agent_card=get_agent_card(host, port), request_handler=request_handler
            )

            # Get the ASGI app from the A2AServer instance
            asgi_app = a2a_server.app()

            # Configure Uvicorn
            # We let Uvicorn handle the ASGI app's lifespan if it has one.
            # Our app_lifespan is for managing mcp_client.
            config = uvicorn.Config(
                app=asgi_app,
                host=host,
                port=port,
                log_level=log_level.lower(),
                lifespan="auto" # "auto" should correctly handle FastAPI/Starlette lifespan
            )
            
            uvicorn_server = uvicorn.Server(config)
            
            print(f"Starting Uvicorn server at http://{host}:{port} with log-level {log_level}...")
            try:
                await uvicorn_server.serve()
            except KeyboardInterrupt:
                print("Server shutdown requested (KeyboardInterrupt).")
            finally:
                print("Uvicorn server has stopped.")
                # Perform any additional cleanup if needed after uvicorn stops
                # The app_lifespan's finally block will handle mcp_client shutdown

    try:
        asyncio.run(run_server_async())
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            print(
                "Critical Error: Attempted to nest asyncio.run(). This should have been prevented.",
                file=sys.stderr
            )
        else:
            print(f"RuntimeError in cli_main: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred in cli_main: {e}", file=sys.stderr)
        sys.exit(1)


def get_agent_card(host: str, port: int) -> AgentCard:
    """Returns the Agent Card for the Weather Agent."""
    capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
    skill = AgentSkill(
        id='weather_search',
        name='Search weather',
        description='Helps with weather in city, or states',
        tags=['weather'],
        examples=['weather in LA, CA'],
    )
    return AgentCard(
        name='Weather Agent',
        description='Helps with weather',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        defaultInputModes=WeatherAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=WeatherAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
        authentication=AgentAuthentication(schemes=['public']),
    )


if __name__ == '__main__':
    cli_main()