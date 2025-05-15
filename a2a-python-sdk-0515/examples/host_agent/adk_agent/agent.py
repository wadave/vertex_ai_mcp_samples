import json
import uuid
from typing import List
import httpx
from typing import Any

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from .remote_agent_connection import RemoteAgentConnections, TaskUpdateCallback
from a2a_client.card_resolver import A2ACardResolver
from a2a_types import (
    AgentCard,
    Message,
    TaskSendParams,
    TextPart,
    Part,
)

from a2a.types import (
    GetTaskResponse,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TaskState,
)

from dotenv import load_dotenv
import os


def convert_part(part: Part, tool_context: ToolContext):
    # Currently only support text parts
    if part.type == "text":
        return part.text

    return f"Unknown type: {part.type}"


def convert_parts(parts: list[Part], tool_context: ToolContext):
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": text}],
            "messageId": uuid.uuid4().hex,
        },
    }

    if task_id:
        payload["message"]["taskId"] = task_id

    if context_id:
        payload["message"]["contextId"] = context_id
    return payload


class RoutingAgent:
    """The Routing agent.

    This is the agent responsible for choosing which remote seller agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        remote_agent_addresses: List[str],
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        for address in remote_agent_addresses:
            card_resolver = A2ACardResolver(address)
            try:
                card = card_resolver.get_agent_card()
                # The URL accessed here should be the same as the one provided in the agent card
                # However, in this demo we are using the URL provided in the key arguments
                remote_connection = RemoteAgentConnections(
                    agent_card=card, agent_url=address
                )
                self.remote_agent_connections[card.name] = remote_connection
                self.cards[card.name] = card
            except httpx.ConnectError:
                print(f"ERROR: Failed to get agent card from : {address}")
        agent_info = []
        for ra in self.list_remote_agents():
            agent_info.append(json.dumps(ra))
        self.agents = "\n".join(agent_info)

    def create_agent(self) -> Agent:
        return Agent(
            model="gemini-2.5-flash-preview-04-17",
            name="Routing_agent",
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                "This Routing agent orchestrates the decomposition of the user asking for weather forecast or airbnb accommodation"
            ),
            tools=[
                self.send_task_new,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        current_agent = self.check_active_agent(context)
        return f"""
        **Role:** You are an expert Routing Delegator. Your primary function is to accurately delegate user inquiries regarding weather or accommodations to the appropriate specialized remote agents.

        **Core Directives:**
        
        * **Task Delegation:** Utilize the `send_task_new` function to assign actionable tasks to remote agents.
        * **Contextual Awareness for Remote Agents:** If a remote agent repeatedly requests user confirmation, assume it lacks access to the         full conversation history. In such cases, enrich the task description with all necessary contextual information relevant to that         specific agent.
        * **Autonomous Agent Engagement:** Never seek user permission before engaging with remote agents. If multiple agents are required to         fulfill a request, connect with them directly without requesting user preference or confirmation.
        * **Transparent Communication:** Always present the complete and detailed response from the remote agent to the user.
        * **User Confirmation Relay:** If a remote agent asks for confirmation, and the user has not already provided it, relay this         confirmation request to the user.
        * **Focused Information Sharing:** Provide remote agents with only relevant contextual information. Avoid extraneous details.
        * **No Redundant Confirmations:** Do not ask remote agents for confirmation of information or actions.
        * **Tool Reliance:** Strictly rely on available tools to address user requests. Do not generate responses based on assumptions. If         information is insufficient, request clarification from the user.
        * **Prioritize Recent Interaction:** Focus primarily on the most recent parts of the conversation when processing requests.
        * **Active Agent Prioritization:** If an active agent is already engaged, route subsequent related requests to that agent using the         appropriate task update tool.
        
        **Agent Roster:**
        
        * Available Agents: `{self.agents}`
        * Currently Active Seller Agent: `{current_agent["active_agent"]}`
                """

    def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            "session_id" in state
            and "session_active" in state
            and state["session_active"]
            and "active_agent" in state
        ):
            return {"active_agent": f"{state['active_agent']}"}
        return {"active_agent": "None"}

    def before_model_callback(self, callback_context: CallbackContext, llm_request):
        state = callback_context.state
        if "session_active" not in state or not state["session_active"]:
            if "session_id" not in state:
                state["session_id"] = str(uuid.uuid4())
            state["session_active"] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.remote_agent_connections:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f"Found agent card: {card.model_dump()}")
            print("=" * 100)
            remote_agent_info.append(
                {"name": card.name, "description": card.description}
            )
        return remote_agent_info

    
    async def send_task_new(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to remote seller agent

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive conversation context summary
                and goal to be achieved regarding user inquiry and purchase request.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f"Agent {agent_name} not found")
        state = tool_context.state
        state["active_agent"] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f"Client not available for {agent_name}")
        if "task_id" in state:
            taskId = state["task_id"]

        else:
            taskId = str(uuid.uuid4())
        task_id = taskId
        sessionId = state["session_id"]
        if "context_id" in state:
            context_id = state["context_id"]
        else:
            context_id = str(uuid.uuid4())

        task: Task
        messageId = ""
        metadata = {}
        if "input_message_metadata" in state:
            metadata.update(**state["input_message_metadata"])
            if "message_id" in state["input_message_metadata"]:
                messageId = state["input_message_metadata"]["message_id"]
        if not messageId:
            messageId = str(uuid.uuid4())

        payload = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": task}],
                "messageId": messageId,
            },
        }

        if task_id:
            payload["message"]["taskId"] = task_id

        if context_id:
            payload["message"]["contextId"] = context_id

        send_response: SendMessageResponse = await client.send_message(payload=payload)
        print("send_response", send_response)

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print("received non-success response. Aborting get task ")
            return

        if not isinstance(send_response.root.result, Task):
            print("received non-task response. Aborting get task ")
            return

        response = send_response
        if hasattr(response, "root"):
            content = response.root.model_dump_json(exclude_none=True)
        else:
            content = response.model_dump(mode="json", exclude_none=True)

        resp = []
        json_content = json.loads(content)
        print(json_content)
        if json_content["result"]:
            for artifact in json_content["result"]["artifacts"]:
                resp.extend(artifact["parts"])
        return resp


load_dotenv()


root_agent = RoutingAgent(
    remote_agent_addresses=[
        os.getenv("AIR_AGENT_URL", "http://localhost:10002"),
        os.getenv("WEA_AGENT_URL", "http://localhost:10001"),
    ]
).create_agent()
