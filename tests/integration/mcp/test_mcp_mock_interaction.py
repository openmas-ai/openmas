"""Integration tests for MCP client-server interaction using mocks.

These tests verify that the McpAgent, McpClientAgent, and McpServerAgent classes
can properly interact without relying on real network communication.
"""

import asyncio
import json
from typing import Any, Dict, Optional

import pytest
from pydantic import BaseModel, Field

from openmas.agent import McpClientAgent, McpServerAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.exceptions import CommunicationError, ServiceNotFoundError
from openmas.testing.mock_communicator import MockCommunicator

# Mark all tests in this module with the 'mcp' marker
pytestmark = pytest.mark.mcp


class WeatherRequest(BaseModel):
    """Request model for the weather tool."""

    location: str = Field(..., description="Location to get weather for")
    unit: str = Field("celsius", description="Temperature unit (celsius or fahrenheit)")


class WeatherResponse(BaseModel):
    """Response model for the weather tool."""

    temperature: float = Field(..., description="Current temperature")
    condition: str = Field(..., description="Weather condition")
    unit: str = Field(..., description="Temperature unit")


class WeatherServer(McpServerAgent):
    """Test server agent that provides weather information."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the weather server.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(
            name="weather_server",
            config={
                "COMMUNICATOR_TYPE": "mock",  # Use mock communicator for testing
                "SERVER_MODE": True,
            },
            **kwargs,
        )

        # Sample weather data
        self.weather_data = {
            "new york": {"temperature": 20.0, "condition": "Sunny"},
            "london": {"temperature": 15.0, "condition": "Cloudy"},
            "tokyo": {"temperature": 25.0, "condition": "Rainy"},
        }

    @mcp_tool(
        name="get_weather",
        description="Get the current weather for a location",
        input_model=WeatherRequest,
        output_model=WeatherResponse,
    )
    async def get_weather(self, location: str, unit: str = "celsius") -> Dict[str, Any]:
        """Get the current weather for a location.

        Args:
            location: The location to get weather for
            unit: The temperature unit (celsius or fahrenheit)

        Returns:
            Dictionary with the weather information

        Raises:
            ValueError: If the location is not found
        """
        # Convert location to lowercase for case-insensitive lookup
        location = location.lower()

        # Check if location is in our data
        if location not in self.weather_data:
            raise ValueError(f"Weather data not available for location: {location}")

        # Get the weather data
        weather = self.weather_data[location]
        temperature = weather["temperature"]

        # Convert temperature if needed
        if unit.lower() == "fahrenheit":
            temperature = (temperature * 9 / 5) + 32

        return {
            "temperature": temperature,
            "condition": weather["condition"],
            "unit": unit.lower(),
        }

    @mcp_prompt(
        name="weather_forecast",
        description="Generate a weather forecast",
    )
    async def weather_forecast(self, location: str, days: int = 1) -> str:
        """Generate a weather forecast for a location.

        Args:
            location: The location to get a forecast for
            days: The number of days to forecast

        Returns:
            A weather forecast message
        """
        location = location.lower()

        # Check if location is in our data
        if location not in self.weather_data:
            return f"No forecast available for {location}."

        # Get the weather data
        weather = self.weather_data[location]

        return (
            f"Weather forecast for {location.title()} for the next {days} day(s):\n"
            f"Current: {weather['condition']} with a temperature of {weather['temperature']}°C."
        )

    @mcp_resource(
        uri="/locations.json",
        name="available_locations",
        description="List of available locations",
        mime_type="application/json",
    )
    async def available_locations(self) -> bytes:
        """Provide a list of available locations.

        Returns:
            JSON data as bytes
        """
        locations = list(self.weather_data.keys())
        data = {"locations": locations}
        return json.dumps(data).encode("utf-8")


class WeatherClient(McpClientAgent):
    """Test client agent that connects to the weather server."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the weather client.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(
            name="weather_client",
            config={
                "COMMUNICATOR_TYPE": "mock",  # Use mock communicator for testing
                "SERVICE_URLS": {"weather_service": "mock://weather_server"},
            },
            **kwargs,
        )


@pytest.fixture
def weather_server() -> WeatherServer:
    """Create a weather server instance."""
    return WeatherServer()


@pytest.fixture
def weather_client() -> WeatherClient:
    """Create a weather client instance."""
    return WeatherClient()


@pytest.fixture
def mock_communicator_setup(weather_server: WeatherServer, weather_client: WeatherClient) -> None:
    """Set up the mock communicators for both server and client.

    This connects the server and client through the mock communicator,
    allowing them to communicate without any real network traffic.
    """
    # Create a shared MockCommunicator "network"
    mock_network = MockCommunicator.get_mock_network()

    # Create server and client communicators
    server_comm = MockCommunicator(
        agent_name=weather_server.name,
        service_urls={},
    )

    client_comm = MockCommunicator(
        agent_name=weather_client.name,
        service_urls={"weather_service": f"mock://{weather_server.name}"},
    )

    # Register server in the mock network
    mock_network.register_server(weather_server.name, server_comm)

    # Set up expectations for test_mcp_client_server_interaction
    client_comm.expect_request(
        target_service="weather_service",
        method="tool/call/get_weather",
        params={"location": "New York", "unit": "celsius"},
        response={"temperature": 20.0, "condition": "Sunny", "unit": "celsius"},
    )

    client_comm.expect_request(
        target_service="weather_service",
        method="tool/call/get_weather",
        params={"location": "London", "unit": "fahrenheit"},
        response={"temperature": 59.0, "condition": "Cloudy", "unit": "fahrenheit"},
    )

    client_comm.expect_request(
        target_service="weather_service",
        method="prompt/get/weather_forecast",
        params={"location": "Tokyo", "days": 3},
        response="Weather forecast for Tokyo for the next 3 day(s):\nCurrent: Rainy with a temperature of 25.0°C.",
    )

    client_comm.expect_request(
        target_service="weather_service",
        method="resource/read",
        params={"uri": "/locations.json"},
        response={"content": '{"locations": ["new york", "london", "tokyo"]}', "mime_type": "application/json"},
    )

    # Paris is not in the data so it should raise an exception
    client_comm.expect_request(
        target_service="weather_service",
        method="tool/call/get_weather",
        params={"location": "Paris"},
        exception=CommunicationError(
            "Failed to call tool 'get_weather': Weather data not available for location: paris",
            target="weather_service",
        ),
    )

    # Set up expectations for test_mcp_client_server_error_handling
    client_comm.expect_request(
        target_service="nonexistent_service",
        method="tool/call/get_weather",
        params={"location": "New York"},
        exception=ServiceNotFoundError("Service 'nonexistent_service' not found", target="nonexistent_service"),
    )

    client_comm.expect_request(
        target_service="weather_service",
        method="tool/call/get_weather",
        params={"location": "Unknown"},
        exception=CommunicationError("Failed to call tool 'get_weather': Location not found", target="weather_service"),
    )

    client_comm.expect_request(
        target_service="weather_service",
        method="tool/call/nonexistent_tool",
        params={},
        exception=CommunicationError("Tool 'nonexistent_tool' not found", target="weather_service"),
    )

    # Set the communicators on the agents
    weather_server.set_communicator(server_comm)
    weather_client.set_communicator(client_comm)


@pytest.mark.asyncio
async def test_mcp_client_server_interaction(
    weather_server: WeatherServer,
    weather_client: WeatherClient,
    mock_communicator_setup: None,
) -> None:
    """Test MCP client-server interaction using mock communicators."""
    # Set up both agents
    await weather_server.setup()
    await weather_client.setup()

    try:
        # Start the server (not needed for mock communicator, but good practice)
        server_task = asyncio.create_task(weather_server.run())

        # Call the get_weather tool
        result = await weather_client.call_tool(
            target_service="weather_service",
            tool_name="get_weather",
            arguments={"location": "New York", "unit": "celsius"},
        )

        # Verify result
        assert isinstance(result, dict)
        assert result["temperature"] == 20.0
        assert result["condition"] == "Sunny"
        assert result["unit"] == "celsius"

        # Test with different unit
        result_f = await weather_client.call_tool(
            target_service="weather_service",
            tool_name="get_weather",
            arguments={"location": "London", "unit": "fahrenheit"},
        )

        # Verify fahrenheit conversion (15°C -> 59°F)
        assert result_f["temperature"] == 59.0
        assert result_f["condition"] == "Cloudy"
        assert result_f["unit"] == "fahrenheit"

        # Get prompt
        forecast = await weather_client.get_prompt(
            target_service="weather_service",
            prompt_name="weather_forecast",
            arguments={"location": "Tokyo", "days": 3},
        )

        # Verify forecast
        assert "Tokyo" in forecast
        assert "3 day" in forecast
        assert "Rainy" in forecast

        # Read resource
        locations_data = await weather_client.read_resource(
            target_service="weather_service",
            uri="/locations.json",
        )

        # Verify locations data
        locations = json.loads(locations_data.decode("utf-8"))
        assert "locations" in locations
        assert set(locations["locations"]) == {"new york", "london", "tokyo"}

        # Test error handling
        with pytest.raises(CommunicationError) as excinfo:
            await weather_client.call_tool(
                target_service="weather_service",
                tool_name="get_weather",
                arguments={"location": "Paris"},  # Not in our data
            )
        assert "Weather data not available" in str(excinfo.value)
    finally:
        # Clean up
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        await weather_server.shutdown()
        await weather_client.shutdown()


@pytest.mark.asyncio
async def test_mcp_client_server_error_handling(
    weather_server: WeatherServer,
    weather_client: WeatherClient,
    mock_communicator_setup: None,
) -> None:
    """Test error handling in MCP client-server interaction."""
    # Set up both agents
    await weather_server.setup()
    await weather_client.setup()

    try:
        # ServiceNotFoundError: Try to call a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await weather_client.call_tool(
                target_service="nonexistent_service",
                tool_name="get_weather",
                arguments={"location": "New York"},
            )

        # MethodNotFoundError: Try to call a non-existent tool
        with pytest.raises(CommunicationError) as excinfo:
            await weather_client.call_tool(
                target_service="weather_service",
                tool_name="nonexistent_tool",
                arguments={},
            )
        # The error message could vary by implementation
        assert "nonexistent_tool" in str(excinfo.value).lower() or "not found" in str(excinfo.value).lower()
    finally:
        await weather_server.shutdown()
        await weather_client.shutdown()


# Create a simple mock network for integration testing
class MockNetwork:
    """Mock network for MCP integration testing."""

    def __init__(self):
        """Initialize the mock network."""
        self.servers = {}

    def register_server(self, name: str, server: Any) -> None:
        """Register a server in the network.

        Args:
            name: Name of the server
            server: Server instance
        """
        self.servers[name] = server

    def get_server(self, name: str) -> Optional[Any]:
        """Get a server by name.

        Args:
            name: Name of the server

        Returns:
            Server instance or None if not found
        """
        return self.servers.get(name)


# Global mock network instance for test
_MOCK_NETWORK = MockNetwork()


# Add get_mock_network method to MockCommunicator
@staticmethod
def get_mock_network():
    """Get the shared mock network instance.

    Returns:
        Shared MockNetwork instance
    """
    global _MOCK_NETWORK
    return _MOCK_NETWORK


# Monkey patch the MockCommunicator class
MockCommunicator.get_mock_network = get_mock_network
