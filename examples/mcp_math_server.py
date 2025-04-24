#!/usr/bin/env python
"""MCP Math Server Example.

This script demonstrates how to create an MCP server that provides
mathematical operations as tools, prompts, and resources.
"""

import asyncio
import logging
import math
import sys
from typing import Any, Dict, Optional, Union

try:
    from anthropic.mcp.types import TextContent

    from simple_mas import McpServerAgent, mcp_prompt, mcp_resource, mcp_tool
    from simple_mas.config import AgentConfig
    from simple_mas.logging import get_logger
except ImportError:
    print("Error: This example requires the simple-mas package and Anthropic Python SDK v1.6.0")
    print("Please install with: poetry install")
    sys.exit(1)

# Create a logger for this server
logger = get_logger("mcp_math_server")


class MathServer(McpServerAgent):
    """A server that provides mathematical operations as MCP tools, prompts, and resources."""

    def __init__(self, config: AgentConfig) -> None:
        """Initialize the Math Server with the given configuration."""
        super().__init__(config)
        self._stored_values: Dict[str, Any] = {}  # Dictionary to store values
        logger.info("Math server initialized")

    # Tool implementations

    @mcp_tool("add")
    async def add(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Add two numbers."""
        result = a + b
        logger.info("Addition: {} + {} = {}".format(a, b, result))
        return result

    @mcp_tool("subtract")
    async def subtract(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Subtract b from a."""
        result = a - b
        logger.info("Subtraction: {} - {} = {}".format(a, b, result))
        return result

    @mcp_tool("multiply")
    async def multiply(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Multiply two numbers."""
        result = a * b
        logger.info("Multiplication: {} * {} = {}".format(a, b, result))
        return result

    @mcp_tool("divide")
    async def divide(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Divide a by b."""
        if b == 0:
            logger.error("Division by zero attempted")
            raise ValueError("Cannot divide by zero")
        result = a / b
        logger.info("Division: {} / {} = {}".format(a, b, result))
        return result

    @mcp_tool("power")
    async def power(self, base: Union[int, float], exponent: Union[int, float]) -> Union[int, float]:
        """Calculate base raised to the power of exponent."""
        result = base**exponent
        logger.info("Power: {}^{} = {}".format(base, exponent, result))
        return result

    @mcp_tool("sqrt")
    async def sqrt(self, x: Union[int, float]) -> float:
        """Calculate the square root of x."""
        if x < 0:
            logger.error("Square root of negative number attempted")
            raise ValueError("Cannot calculate square root of a negative number")
        result = math.sqrt(x)
        logger.info("Square root: √{} = {}".format(x, result))
        return result

    @mcp_tool("get_weather")
    async def get_weather(self, city: str) -> Dict[str, Any]:
        """
        Get mock weather information for a city.

        Args:
            city: Name of the city

        Returns:
            A dictionary with weather information
        """
        # Mock weather data (in a real application, this would call a weather API)
        weather_data = {
            "new york": {"temperature": 72, "condition": "Partly Cloudy", "humidity": 65},
            "london": {"temperature": 62, "condition": "Rainy", "humidity": 80},
            "tokyo": {"temperature": 85, "condition": "Sunny", "humidity": 70},
            "sydney": {"temperature": 68, "condition": "Clear", "humidity": 55},
            "paris": {"temperature": 70, "condition": "Cloudy", "humidity": 60},
        }

        city_lower = city.lower()
        if city_lower in weather_data:
            logger.info("Retrieved weather for {}: {}".format(city, weather_data[city_lower]))
            return weather_data[city_lower]
        else:
            logger.warning("No weather data available for {}".format(city))
            return {"error": "No weather data available for {}".format(city)}

    @mcp_tool("store")
    async def store(self, key: str, value: Any) -> bool:
        """
        Store a value with the given key.

        Args:
            key: The key to store the value under
            value: The value to store

        Returns:
            True if the operation was successful
        """
        self._stored_values[key] = value
        logger.info("Storing value for key: {}".format(key))
        return True

    @mcp_tool("retrieve")
    async def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve a stored value by key.

        Args:
            key: The key to retrieve

        Returns:
            The stored value, or None if the key doesn't exist
        """
        if key in self._stored_values:
            value = self._stored_values[key]
            logger.info("Retrieved value for key: {}".format(key))
            return value
        else:
            logger.warning("No value found for key '{}'".format(key))
            return None

    # Prompt implementations

    @mcp_prompt("greeting")
    async def greeting(self, name: str) -> TextContent:
        """
        A simple greeting prompt that welcomes the user.

        Args:
            name: The name to greet

        Returns:
            A greeting message
        """
        logger.info("Generating greeting for: {}".format(name))
        greeting_message = (
            "Hello, {}! Welcome to the MCP Math Server. "
            "I can help with various math operations through my tools, "
            "prompts, and resources. Feel free to explore what I can do!"
        ).format(name)
        return TextContent(text=greeting_message)

    @mcp_prompt("circle_area")
    async def circle_area(self, radius: Union[int, float]) -> TextContent:
        """
        Calculate the area of a circle and return a formatted explanation.

        Args:
            radius: The radius of the circle

        Returns:
            A formatted explanation of the calculation
        """
        if radius < 0:
            logger.error("Negative radius ({}) provided for circle area calculation".format(radius))
            return TextContent(text="Error: Circle radius cannot be negative.")

        # Get PI from resources
        pi = await self.pi()

        # Calculate the area
        area = pi * (radius**2)

        logger.info("Calculated circle area for radius {}: {}".format(radius, area))

        # Format the explanation
        explanation = (
            "To calculate the area of a circle with radius r = {}:\n\n"
            "Formula: Area = π × r²\n"
            "Area = {} × ({})²\n"
            "Area = {} × {}\n"
            "Area = {}\n\n"
            "The area of the circle is {} square units."
        ).format(radius, pi, radius, pi, radius**2, area, area)

        return TextContent(text=explanation)

    @mcp_prompt("quadratic_equation")
    async def quadratic_equation(self, a: Union[int, float], b: Union[int, float], c: Union[int, float]) -> TextContent:
        """
        Solve a quadratic equation and explain the steps.

        Args:
            a: Coefficient of x²
            b: Coefficient of x
            c: Constant term

        Returns:
            A detailed explanation of how to solve the equation
        """
        logger.info("Solving quadratic equation: {}x² + {}x + {} = 0".format(a, b, c))

        # Format the equation
        if b >= 0:
            b_term = "+ {}x ".format(b)
        else:
            b_term = "- {}x ".format(abs(b))

        if c >= 0:
            c_term = "+ {} = 0".format(c)
        else:
            c_term = "- {} = 0".format(abs(c))

        equation = "{}x² {}{}".format(a, b_term, c_term)

        # Calculate the discriminant
        discriminant = (b**2) - (4 * a * c)

        # Prepare the solution explanation
        explanation = [
            "To solve the quadratic equation {}:".format(equation),
            "",
            "Step 1: Calculate the discriminant (Δ) using the formula:",
            "Δ = b² - 4ac",
            "Δ = ({})² - 4({})({})".format(b, a, c),
            "Δ = {} - {}".format(b**2, 4 * a * c),
            "Δ = {}".format(discriminant),
            "",
        ]

        # Check the discriminant to determine the nature of the roots
        if discriminant < 0:
            explanation.extend(
                [
                    "Step 2: Since the discriminant is negative, the equation has no real solutions.",
                    "The solutions are complex numbers.",
                ]
            )

            # Calculate the complex roots
            real_part = -b / (2 * a)
            imaginary_part = math.sqrt(abs(discriminant)) / (2 * a)

            explanation.extend(
                [
                    "",
                    "For complex solutions, we use the formula:",
                    "x = (-b ± i√|Δ|) / (2a)",
                    "x = ({} ± i√{}) / (2 × {})".format(-b, abs(discriminant), a),
                    "x = ({} ± i√{}) / {}".format(-b, abs(discriminant), 2 * a),
                    "x = {} ± {}i".format(real_part, imaginary_part),
                    "",
                    "Therefore, the solutions are:",
                    "x₁ = {} + {}i".format(real_part, imaginary_part),
                    "x₂ = {} - {}i".format(real_part, imaginary_part),
                ]
            )

        elif discriminant == 0:
            explanation.extend(
                [
                    "Step 2: Since the discriminant is zero, the equation has exactly one real solution.",
                    "This means there is one repeated root.",
                ]
            )

            # Calculate the single root
            x = -b / (2 * a)

            explanation.extend(
                [
                    "",
                    "For the case of a repeated root, we use the formula:",
                    "x = -b / (2a)",
                    "x = ({}) / (2 × {})".format(-b, a),
                    "x = {} / {}".format(-b, 2 * a),
                    "x = {}".format(x),
                    "",
                    "Therefore, the solution is x = {} (a repeated root)".format(x),
                ]
            )

        else:  # discriminant > 0
            explanation.extend(
                [
                    "Step 2: Since the discriminant is positive, the equation has two distinct real solutions.",
                    "We will use the quadratic formula.",
                ]
            )

            # Calculate the two roots
            x1 = (-b + math.sqrt(discriminant)) / (2 * a)
            x2 = (-b - math.sqrt(discriminant)) / (2 * a)

            explanation.extend(
                [
                    "",
                    "Using the quadratic formula: x = (-b ± √Δ) / (2a)",
                    "x = ({} ± √{}) / (2 × {})".format(-b, discriminant, a),
                    "x = ({} ± √{}) / {}".format(-b, discriminant, 2 * a),
                    "x = ({} ± {}) / {}".format(-b, math.sqrt(discriminant), 2 * a),
                    "",
                    "For x₁ = (-b + √Δ) / (2a):",
                    "x₁ = ({} + {}) / {}".format(-b, math.sqrt(discriminant), 2 * a),
                    "x₁ = {} / {}".format(-b + math.sqrt(discriminant), 2 * a),
                    "x₁ = {}".format(x1),
                    "",
                    "For x₂ = (-b - √Δ) / (2a):",
                    "x₂ = ({} - {}) / {}".format(-b, math.sqrt(discriminant), 2 * a),
                    "x₂ = {} / {}".format(-b - math.sqrt(discriminant), 2 * a),
                    "x₂ = {}".format(x2),
                    "",
                    "Therefore, the solutions are x₁ = {} and x₂ = {}".format(x1, x2),
                ]
            )

        return TextContent(text="\n".join(explanation))

    # Resource implementations

    @mcp_resource("pi")
    async def pi(self) -> float:
        """Return the value of π."""
        logger.info("Retrieved Pi value")
        return math.pi

    @mcp_resource("e")
    async def e(self) -> float:
        """Return the value of Euler's number (e)."""
        logger.info("Retrieved Euler's number")
        return math.e

    @mcp_resource("greeting_message")
    async def greeting_message(self) -> str:
        """Return a general greeting message for the server."""
        logger.info("Greeting message resource requested")
        return "Welcome to the Math Server! This server provides mathematical operations as tools and resources."

    @mcp_resource("server_info")
    async def server_info(self) -> str:
        """Return information about the server."""
        logger.info("Server info resource requested")
        return "Math Server v1.0 - An MCP server that provides mathematical operations."

    @mcp_resource("server_time")
    async def server_time(self) -> str:
        """Return the current server time."""
        import datetime

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("Server time requested: {}".format(current_time))
        return current_time


async def main() -> None:
    """Run the MCP Math Server."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Create an agent configuration
    config = AgentConfig(host="localhost", port=8000)

    # Create and start the math server
    math_server = MathServer(config)
    logger.info("Starting MCP Math Server on {}:{}".format(config.host, config.port))
    await math_server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server terminated by user")
        print("Server terminated by user")
    except Exception as e:
        logger.error("Server error: {}".format(e), exc_info=True)
        print("Error: {}".format(e))
