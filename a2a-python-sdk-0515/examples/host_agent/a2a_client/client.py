
import httpx
import base64
from typing import Any, AsyncIterable
from a2a_types import (
    AgentCard,
    SendTaskRequest,
    SendTaskResponse,
    JSONRPCRequest,
    A2AClientHTTPError,
    A2AClientJSONError,
    SendTaskStreamingResponse,
)
import json
from uuid import uuid4
from a2a.types import (
    A2ARequest,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    GetTaskResponse,
    GetTaskRequest,
    TaskQueryParams,
    
)
class A2AClient:
    def __init__(self, agent_card: AgentCard, auth: str, agent_url: str):
        # The URL accessed here should be the same as the one provided in the agent card
        # However, in this demo we are using the URL provided in the key arguments
        self.url = agent_url
        # self.url = agent_card.url
        self.auth_header = None

        if agent_card.authentication:
            if len(agent_card.authentication.schemes) > 1:
                raise ValueError(
                    "Only one A2A client authentication scheme is supported for now"
                )
            elif len(agent_card.authentication.schemes) == 1:
                if agent_card.authentication.schemes[0].lower() == "bearer":
                    self.auth_header = f"Bearer {auth}"
                elif agent_card.authentication.schemes[0].lower() == "basic":
                    # Encode auth string to base64 for Basic authentication
                    encoded_auth = base64.b64encode(auth.encode()).decode()
                    self.auth_header = f"Basic {encoded_auth}"
                elif agent_card.authentication.schemes[0].lower() == "public":
                    # Encode auth string to base64 for Basic authentication
                    self.auth_header = None
                else:
                    raise ValueError("Unsupported authentication scheme")

    async def send_task(self, payload: dict[str, Any]) -> SendTaskResponse:
        request = SendTaskRequest(params=payload)
        return SendTaskResponse(**await self._send_request(request))
    
    async def send_message(
        self, payload: dict[str, Any], request_id: str | int = uuid4().hex
    ) -> SendMessageResponse:
        request = SendMessageRequest(
            id=request_id, params=MessageSendParams.model_validate(payload)
        )
        return SendMessageResponse(
            **await self._send_request(A2ARequest(request))
        )
        
    async def get_task(
        self, payload: dict[str, Any], request_id: str | int = uuid4().hex
    ) -> GetTaskResponse:
        request = GetTaskRequest(
            id=request_id, params=TaskQueryParams.model_validate(payload)
        )
        return GetTaskResponse(**await self._send_request(A2ARequest(request)))
    
    async def send_task_streaming(
        self, payload: dict[str, Any]
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        raise NotImplementedError("Streaming is not supported for now")

    async def _send_request(self, request: JSONRPCRequest) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                # Image generation could take time, adding timeout
                print(f"Send Remote Agent Task Request: {request.model_dump(mode='json')}")
                print("=" * 100)
                request_kwargs = {
                    "url": self.url,
                    "json": request.model_dump(mode='json'),
                    "timeout": 30,
                }
                if self.auth_header:
                    request_kwargs["headers"] = {"Authorization": self.auth_header}

                response = await client.post(**request_kwargs)
                response.raise_for_status()
                print(f"Send Remote Agent Task Response: {response.json()}")
                print("=" * 100)
                return response.json()
            except httpx.HTTPStatusError as e:
                raise A2AClientHTTPError(e.response.status_code, str(e)) from e
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(str(e)) from e
