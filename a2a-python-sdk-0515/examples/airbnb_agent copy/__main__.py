import os
import sys

import click

from agent import AirbnbAgent
from agent_executor import AirbnbAgentExecutor
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
@click.option('--port', 'port', default=10002)
def main(host: str, port: int):
    if not os.getenv('GOOGLE_API_KEY'):
        print('GOOGLE_API_KEY environment variable not set.')
        sys.exit(1)

    request_handler = DefaultA2ARequestHandler(
        agent_executor=AirbnbAgentExecutor()
    )

    server = A2AServer(
        agent_card=get_agent_card(host, port), request_handler=request_handler
    )
    server.start(host=host, port=port)


def get_agent_card(host: str, port: int):
    """Returns the Agent Card for the Currency Agent."""
    capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
    skill = AgentSkill(
        id='airbnb_search',
        name='Search airbnb accommodation',
        description='Helps with accommodation search using airbnb',
        tags=['airbnb accommodation'],
        examples=['Please find a room in LA, CA, April 15, 2025, checkout date is april 18, 2 adults'],
    )
    return AgentCard(
        name='Airbnb Agent',
        description='Helps with searching accommodation',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        defaultInputModes=AirbnbAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=AirbnbAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
        authentication=AgentAuthentication(schemes=['public']),
    )


if __name__ == '__main__':
    main()
