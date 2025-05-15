import os
import sys

import click

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


load_dotenv()


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10001)
def main(host: str, port: int):
    if not os.getenv('GOOGLE_API_KEY'):
        print('GOOGLE_API_KEY environment variable not set.')
        sys.exit(1)

    request_handler = DefaultA2ARequestHandler(
        agent_executor=WeatherAgentExecutor()
    )

    server = A2AServer(
        agent_card=get_agent_card(host, port), request_handler=request_handler
    )
    server.start(host=host, port=port)


def get_agent_card(host: str, port: int):
    """Returns the Agent Card for the Currency Agent."""
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
    main()
