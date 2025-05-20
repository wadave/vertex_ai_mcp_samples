import logging
import os
from contextlib import asynccontextmanager

import click
import uvicorn
from dotenv import load_dotenv

from adk_agent import create_agent
from adk_agent_executor import ADKAgentExecutor
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from custom_mcp_toolset import CustomMCPToolset

from starlette.applications import Starlette

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure weather_server.py is in the current working directory when __main__.py is run,
# or adjust the path in args.
mcp_connection_params = StdioServerParameters(
    command="python",  # Or "python3", ensure it's in your PATH
    args=["./weather_server.py"],  # Path relative to where __main__.py is executed
)


@asynccontextmanager
async def app_lifespan(app: Starlette):
    logger.info("Lifespan: Startup sequence initiated.")
    async with CustomMCPToolset(connection_params=mcp_connection_params) as toolset:
        logger.info("Lifespan: MCPToolset context entered. Loading tools...")
        loaded_tools = await toolset.load_tools()
        logger.info(f"Lifespan: {len(loaded_tools)} MCPTool(s) loaded successfully.")
        app.state.mcp_tools = (
            loaded_tools  # Storing for potential access, though primarily used for init
        )

        agent_card_from_state = app.state.agent_card

        _adk_agent = create_agent(mcp_tools=loaded_tools)
        app.state.adk_agent = _adk_agent
        logger.info("Lifespan: ADK Agent created.")

        _runner = Runner(
            app_name=agent_card_from_state.name,
            agent=_adk_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        app.state.runner = _runner
        logger.info("Lifespan: ADK Runner initialized.")

        _agent_executor = ADKAgentExecutor(_runner, agent_card_from_state)
        app.state.agent_executor = _agent_executor
        logger.info("Lifespan: ADKAgentExecutor initialized.")

        _request_handler = DefaultRequestHandler(
            agent_executor=_agent_executor, task_store=InMemoryTaskStore()
        )
        app.state.http_handler = _request_handler
        logger.info("Lifespan: DefaultRequestHandler initialized.")

        # Create an instance of A2AStarletteApplication
        a2a_app_builder = A2AStarletteApplication(
            agent_card=agent_card_from_state, http_handler=_request_handler
        )

        # Build the Starlette app from the A2AStarletteApplication instance
        # to reliably access its routes list.
        built_a2a_starlette_app = a2a_app_builder.build()

        logger.info(
            f"Lifespan: Adding routes from A2A application. Number of routes to process: {len(built_a2a_starlette_app.routes)}"
        )

        existing_route_paths = {
            route.path for route in app.router.routes if hasattr(route, "path")
        }

        # Iterate over the .routes attribute of the BUILT Starlette app
        for route in built_a2a_starlette_app.routes:
            # Ensure the main app doesn't already have a route with the same path
            if hasattr(route, "path") and route.path not in existing_route_paths:
                app.router.routes.append(route)
                existing_route_paths.add(route.path)
                logger.debug(
                    f"Lifespan: Added route: {getattr(route, 'name', 'Unnamed route')} Path: {route.path}"
                )
            elif not hasattr(route, "path"):
                # Handle cases like WebSocketRoute or Mount which might not have a simple .path for this check
                # For simplicity, we'll just add them if they don't have a .path to check for duplicates by path.
                # A more robust check might involve route names or types.
                app.router.routes.append(route)
                logger.debug(
                    f"Lifespan: Added route without simple path: {getattr(route, 'name', 'Unnamed route')}"
                )
            else:
                logger.debug(f"Lifespan: Skipped duplicate route Path: {route.path}")

        logger.info(
            "Lifespan: A2A routes processed and potentially added to the application."
        )

        logger.info("Lifespan: Startup sequence complete. Application is ready.")
        yield  # Application runs after this point

    logger.info(
        "Lifespan: Shutdown sequence initiated. MCPToolset context exited, resources released."
    )


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10001, type=int)
def main(host: str, port: int):
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE" and not os.getenv(
        "GOOGLE_API_KEY"
    ):
        logger.warning(
            "GOOGLE_API_KEY environment variable not set and GOOGLE_GENAI_USE_VERTEXAI is not TRUE. "
            "Ensure your environment is configured for Google Generative AI, especially for Gemini models."
        )

    skill = AgentSkill(
        id="weather_search",
        name="Search weather",
        description="Helps with weather in city, or states",
        tags=["weather"],
        examples=["weather in LA, CA"],
    )

    agent_card = AgentCard(
        name="Weather Agent",
        description="Helps with weather",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    app = Starlette(lifespan=app_lifespan)
    app.state.agent_card = agent_card

    logger.info(f"Starting Uvicorn server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
