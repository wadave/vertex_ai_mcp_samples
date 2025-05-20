from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    SseServerParams,
    MCPTool,
)
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any, List, Optional, Tuple, Type

# Attempt to import MCP Tool from the MCP library, and hints user to upgrade
# their Python version to 3.10 if it fails.
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.types import ListToolsResult
except ImportError as e:
    import sys

    if sys.version_info < (3, 10):
        raise ImportError(
            "MCP Tool requires Python 3.10 or above. Please upgrade your Python"
            " version."
        ) from e
    else:
        raise e


class CustomMCPToolset(MCPToolset):
    """Define custom MCPToolset."""

    def __init__(
        self,
        *,
        connection_params: StdioServerParameters | SseServerParams,
    ):
        super().__init__(connection_params=connection_params)
        self._custom_exit_stack = AsyncExitStack()
        print(f"LOG: CustomMCPToolset.__init__ completed.")

    async def _initialize_custom_session(self) -> ClientSession:
        print("LOG: CustomMCPToolset._initialize_custom_session called.")
        param_attr_name_to_try = "_connection_params"
        if not hasattr(self, param_attr_name_to_try):
            print(
                f"LOG: CustomMCPToolset - self.{param_attr_name_to_try} not found, trying 'connection_params'"
            )
            param_attr_name_to_try = "connection_params"
            if not hasattr(self, param_attr_name_to_try):
                raise AttributeError(
                    "CRITICAL: CustomMCPToolset instance has neither '_connection_params' nor 'connection_params' "
                    "after base __init__ call."
                )
        current_connection_params = getattr(self, param_attr_name_to_try)
        print(
            f"LOG: CustomMCPToolset using self.{param_attr_name_to_try}: {type(current_connection_params).__name__}"
        )

        if isinstance(current_connection_params, StdioServerParameters):
            client = stdio_client(current_connection_params)
        elif isinstance(current_connection_params, SseServerParams):
            client = sse_client(
                url=current_connection_params.url,
                headers=current_connection_params.headers,
                timeout=current_connection_params.timeout,
                sse_read_timeout=current_connection_params.sse_read_timeout,
            )
        else:
            raise ValueError(
                f"CustomMCPToolset: Invalid type for stored {param_attr_name_to_try}."
            )

        transports = await self._custom_exit_stack.enter_async_context(client)
        self.session = await self._custom_exit_stack.enter_async_context(
            ClientSession(*transports)
        )
        await self.session.initialize()
        if not self.session:
            raise RuntimeError("CustomMCPToolset: Session initialization failed.")
        print("LOG: CustomMCPToolset._initialize_custom_session successful.")
        return self.session

    async def _shutdown_custom_session(self):
        print("LOG: CustomMCPToolset._shutdown_custom_session called.")
        await self._custom_exit_stack.aclose()

    async def __aenter__(self):
        print("LOG: CustomMCPToolset.__aenter__ called.")
        try:
            await self._initialize_custom_session()
            return self
        except Exception:
            await self._shutdown_custom_session()
            raise

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        print(f"LOG: CustomMCPToolset.__aexit__ called (exception: {exc_type}).")
        try:
            await self._shutdown_custom_session()
        finally:
            base_super = super()
            if hasattr(base_super, "__aexit__") and callable(
                getattr(base_super, "__aexit__")
            ):
                print("LOG: CustomMCPToolset calling super().__aexit__.")
                await base_super.__aexit__(exc_type, exc, tb)
            elif hasattr(base_super, "_exit") and callable(
                getattr(base_super, "_exit")
            ):
                print(
                    "LOG: CustomMCPToolset - super() has no __aexit__. Calling super()._exit() as fallback."
                )
                await base_super._exit()  # type: ignore
            else:
                print(
                    "LOG: CustomMCPToolset - super() has no __aexit__ or _exit method. Base cleanup may be incomplete."
                )
        print("LOG: CustomMCPToolset.__aexit__ completed.")

    # This method overrides the base class's load_tools
    async def load_tools(self) -> List[MCPTool]:
        """Loads all tools from the MCP Server.

        Returns:
          A list of MCPTools imported from the MCP Server.
        """
        tools_response: ListToolsResult = await self.session.list_tools()
        return [
            MCPTool(mcp_tool=tool, mcp_session=self.session, mcp_session_manager=self)
            for tool in tools_response.tools
        ]

    @classmethod
    async def from_server(
        cls,
        *,
        connection_params: StdioServerParameters | SseServerParams,
        async_exit_stack: Optional[AsyncExitStack] = None,
    ) -> Tuple[List[MCPTool], AsyncExitStack]:
        print(f"LOG: CustomMCPToolset.from_server (for {cls.__name__}) called.")
        toolset = cls(connection_params=connection_params)
        effective_exit_stack = async_exit_stack or AsyncExitStack()
        await effective_exit_stack.enter_async_context(toolset)
        tools = await toolset.load_tools()  # Calls CustomMCPToolset.load_tools
        return (tools, effective_exit_stack)
