#!/usr/bin/env python
"""MCP Math Client Example.

This example demonstrates a client application using the MCP protocol
to connect to the math server and use its capabilities.

To run:
    poetry run python examples/mcp_math_client.py
"""
import asyncio
import logging
import sys
from typing import Any, Dict, List

from simple_mas import McpAgent
from simple_mas.logging import configure_logging, get_logger


class MathClient(McpAgent):
    """Math client that connects to the math server."""

    def __init__(self, name: str):
        """Initialize the math client."""
        super().__init__(name)
        self.logger = get_logger(__name__)
        self.server_service_id = None

    async def connect_to_server(self, host: str = "localhost", port: int = 8000):
        """Connect to the math server.

        Args:
            host: Server host
            port: Server port
        """
        self.logger.info(f"Connecting to math server at {host}:{port}")
        self.server_service_id = "math_server"
        await self.connect_to_service(
            service_name=self.server_service_id,
            host=host,
            port=port,
        )
        self.logger.info(f"Connected to math server (service ID: {self.server_service_id})")

    async def list_server_tools(self) -> List[Dict[str, Any]]:
        """List all tools available on the server.

        Returns:
            List of tool descriptions
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info("Listing server tools")
        tools = await self.list_tools(self.server_service_id)

        for i, tool in enumerate(tools, 1):
            self.logger.info(f"Tool {i}: {tool['name']} - {tool['description']}")

        return tools

    async def list_server_prompts(self) -> List[Dict[str, Any]]:
        """List all prompts available on the server.

        Returns:
            List of prompt descriptions
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info("Listing server prompts")
        prompts = await self.list_prompts(self.server_service_id)

        for i, prompt in enumerate(prompts, 1):
            self.logger.info(f"Prompt {i}: {prompt['name']} - {prompt['description']}")

        return prompts

    async def list_server_resources(self) -> List[Dict[str, Any]]:
        """List all resources available on the server.

        Returns:
            List of resource descriptions
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info("Listing server resources")
        resources = await self.list_resources(self.server_service_id)

        for i, resource in enumerate(resources, 1):
            self.logger.info(f"Resource {i}: {resource['name']} - {resource['description']}")

        return resources

    async def add_numbers(self, a: float, b: float) -> Dict[str, Any]:
        """Add two numbers using the server.

        Args:
            a: First number
            b: Second number

        Returns:
            Server response with the result
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Adding {a} + {b} using server")
        return await self.call_tool(service_name=self.server_service_id, tool_name="add", parameters={"a": a, "b": b})

    async def subtract_numbers(self, a: float, b: float) -> Dict[str, Any]:
        """Subtract b from a using the server.

        Args:
            a: First number
            b: Second number

        Returns:
            Server response with the result
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Subtracting {b} from {a} using server")
        return await self.call_tool(
            service_name=self.server_service_id, tool_name="subtract", parameters={"a": a, "b": b}
        )

    async def multiply_numbers(self, a: float, b: float) -> Dict[str, Any]:
        """Multiply two numbers using the server.

        Args:
            a: First number
            b: Second number

        Returns:
            Server response with the result
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Multiplying {a} × {b} using server")
        return await self.call_tool(
            service_name=self.server_service_id, tool_name="multiply", parameters={"a": a, "b": b}
        )

    async def divide_numbers(self, a: float, b: float) -> Dict[str, Any]:
        """Divide a by b using the server.

        Args:
            a: Numerator
            b: Denominator

        Returns:
            Server response with the result

        Raises:
            ValueError: If b is zero (server will reject)
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        if b == 0:
            raise ValueError("Cannot divide by zero")

        self.logger.info(f"Dividing {a} ÷ {b} using server")
        return await self.call_tool(
            service_name=self.server_service_id, tool_name="divide", parameters={"a": a, "b": b}
        )

    async def calculate_power(self, base: float, exponent: float) -> Dict[str, Any]:
        """Calculate power using the server.

        Args:
            base: Base number
            exponent: Exponent

        Returns:
            Server response with the result
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Calculating {base}^{exponent} using server")
        return await self.call_tool(
            service_name=self.server_service_id, tool_name="power", parameters={"base": base, "exponent": exponent}
        )

    async def calculate_sqrt(self, x: float) -> Dict[str, Any]:
        """Calculate square root using the server.

        Args:
            x: Number to calculate square root of

        Returns:
            Server response with the result

        Raises:
            ValueError: If x is negative (server will reject)
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        if x < 0:
            raise ValueError("Cannot calculate square root of negative number")

        self.logger.info(f"Calculating sqrt({x}) using server")
        return await self.call_tool(service_name=self.server_service_id, tool_name="sqrt", parameters={"x": x})

    async def get_weather(self, location: str, unit: str = "celsius") -> Dict[str, Any]:
        """Get weather information from the server.

        Args:
            location: Location to get weather for
            unit: Temperature unit (celsius or fahrenheit)

        Returns:
            Weather information
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Getting weather for {location} in {unit}")
        return await self.call_tool(
            service_name=self.server_service_id,
            tool_name="get_weather",
            parameters={"location": location, "unit": unit},
        )

    async def store_value(self, key: str, value: str) -> Dict[str, Any]:
        """Store a value on the server.

        Args:
            key: Key to store the value under
            value: Value to store

        Returns:
            Server response
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Storing value for key: {key}")
        return await self.call_tool(
            service_name=self.server_service_id, tool_name="store", parameters={"key": key, "value": value}
        )

    async def retrieve_value(self, key: str) -> Dict[str, Any]:
        """Retrieve a value from the server.

        Args:
            key: Key to retrieve the value for

        Returns:
            Server response with the value
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Retrieving value for key: {key}")
        return await self.call_tool(service_name=self.server_service_id, tool_name="retrieve", parameters={"key": key})

    async def get_server_info(self) -> Dict[str, Any]:
        """Get information about the server.

        Returns:
            Server information
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info("Getting server information")
        return await self.call_tool(service_name=self.server_service_id, tool_name="server_info", parameters={})

    async def get_circle_area_prompt(self, radius: float) -> str:
        """Get a prompt for calculating the area of a circle.

        Args:
            radius: Radius of the circle

        Returns:
            Prompt text
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Getting circle area prompt for radius: {radius}")
        result = await self.get_prompt(
            service_name=self.server_service_id, prompt_name="circle_area_prompt", parameters={"radius": radius}
        )
        return result

    async def get_quadratic_equation_prompt(self, a: float, b: float, c: float) -> str:
        """Get a prompt for solving a quadratic equation.

        Args:
            a: Coefficient of x²
            b: Coefficient of x
            c: Constant term

        Returns:
            Prompt text
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info(f"Getting quadratic equation prompt for: {a}x² + {b}x + {c} = 0")
        result = await self.get_prompt(
            service_name=self.server_service_id,
            prompt_name="quadratic_equation_prompt",
            parameters={"a": a, "b": b, "c": c},
        )
        return result

    async def get_pi(self) -> str:
        """Get the value of Pi from the server.

        Returns:
            Pi value as string
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info("Getting Pi value from server")
        result = await self.get_resource(service_name=self.server_service_id, resource_name="pi")
        return result

    async def get_e(self) -> str:
        """Get the value of e from the server.

        Returns:
            e value as string
        """
        if not self.server_service_id:
            raise ValueError("Not connected to the math server")

        self.logger.info("Getting e value from server")
        result = await self.get_resource(service_name=self.server_service_id, resource_name="e")
        return result


async def main():
    """Run the math client demo."""
    # Setup logging
    configure_logging(log_level=logging.INFO)
    logger = get_logger(__name__)

    # Create client agent
    client = MathClient("math_client")

    try:
        # Start client
        await client.start()
        logger.info("Math client started")

        # Connect to server
        await client.connect_to_server()

        # List available server capabilities
        logger.info("Exploring server capabilities:")
        await client.list_server_tools()
        await client.list_server_prompts()
        await client.list_server_resources()

        # Perform some calculations
        logger.info("\nPerforming calculations:")

        # Addition
        result = await client.add_numbers(5, 3)
        logger.info(f"5 + 3 = {result['result']}")

        # Subtraction
        result = await client.subtract_numbers(10, 4)
        logger.info(f"10 - 4 = {result['result']}")

        # Multiplication
        result = await client.multiply_numbers(6, 7)
        logger.info(f"6 × 7 = {result['result']}")

        # Division
        result = await client.divide_numbers(20, 5)
        logger.info(f"20 ÷ 5 = {result['result']}")

        # Power
        result = await client.calculate_power(2, 8)
        logger.info(f"2^8 = {result['result']}")

        # Square root
        result = await client.calculate_sqrt(16)
        logger.info(f"√16 = {result['result']}")

        # Get weather
        logger.info("\nGetting weather information:")
        weather = await client.get_weather("New York", "celsius")
        logger.info(
            f"Weather in {weather['location']}: {weather['temperature']}, "
            f"{weather['conditions']}, Humidity: {weather['humidity']}"
        )

        # Store and retrieve values
        logger.info("\nTesting key-value storage:")
        await client.store_value("favorite_number", "42")
        result = await client.retrieve_value("favorite_number")
        logger.info(f"Retrieved value for 'favorite_number': {result['value']}")

        # Get server info
        logger.info("\nGetting server information:")
        info = await client.get_server_info()
        logger.info(f"Server name: {info['name']}, Version: {info['version']}")
        logger.info(f"Platform: {info['platform']}")
        logger.info(f"Server time: {info['time']}")

        # Get prompts
        logger.info("\nGetting prompts:")
        circle_prompt = await client.get_circle_area_prompt(5)
        logger.info("Circle area prompt:")
        logger.info(circle_prompt)

        quadratic_prompt = await client.get_quadratic_equation_prompt(1, -3, 2)
        logger.info("\nQuadratic equation prompt:")
        logger.info(quadratic_prompt)

        # Get resources
        logger.info("\nGetting resources:")
        pi_value = await client.get_pi()
        logger.info(f"Pi = {pi_value}")

        e_value = await client.get_e()
        logger.info(f"e = {e_value}")

    except Exception as e:
        logger.error(f"Error in math client: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Disconnect from server and stop client
        if client.server_service_id:
            await client.disconnect_from_service(client.server_service_id)

        await client.stop()
        logger.info("Math client stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient terminated by user")
        sys.exit(0)
