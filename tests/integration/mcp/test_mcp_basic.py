"""Basic integration tests for MCP decorators and functionality.

These tests verify that the MCP decorators and agent classes work correctly,
focusing on core functionality without complex network communication.
This minimizes issues with permissions, networking, and temporary files.
"""

import json
from typing import Any, Dict, Optional

import pytest
from pydantic import BaseModel, Field

from openmas.agent import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.config import AgentConfig

# Mark all tests in this module with the 'mcp' marker
pytestmark = pytest.mark.mcp


class BasicCalculator(McpAgent):
    """A basic calculator agent for testing MCP decorators."""

    @mcp_tool(name="add", description="Add two numbers")
    async def add(self, a: int, b: int) -> Dict[str, int]:
        """Add two numbers and return the result.

        Args:
            a: First number
            b: Second number

        Returns:
            Dictionary with the result
        """
        return {"result": a + b}

    @mcp_tool(name="subtract", description="Subtract two numbers")
    async def subtract(self, a: int, b: int) -> Dict[str, int]:
        """Subtract b from a and return the result.

        Args:
            a: First number
            b: Second number to subtract from a

        Returns:
            Dictionary with the result
        """
        return {"result": a - b}

    @mcp_prompt(name="math_question", description="Generate a math question")
    async def math_question(self, difficulty: str, topic: str) -> str:
        """Generate a math question with the given difficulty and topic.

        Args:
            difficulty: The difficulty level (easy, medium, hard)
            topic: The math topic (addition, subtraction, etc.)

        Returns:
            A math question
        """
        return f"Here's a {difficulty} question about {topic}: what is 2{'+' if topic == 'addition' else '-'}2?"

    @mcp_resource(
        uri="/data.json",
        name="sample_data",
        description="Sample JSON data",
        mime_type="application/json",
    )
    async def sample_data(self) -> bytes:
        """Provide sample JSON data.

        Returns:
            JSON data as bytes
        """
        data = {"name": "Sample Data", "values": [1, 2, 3, 4, 5]}
        return json.dumps(data).encode("utf-8")


# Fixtures for the tests
@pytest.fixture
def simple_calculator() -> BasicCalculator:
    """Create a simple calculator instance."""
    config = AgentConfig(
        name="calculator",
        communicator_type="mock",
        service_urls={},
    )
    return BasicCalculator(config=config)


@pytest.mark.asyncio
async def test_mcp_decorators_discovery(simple_calculator: BasicCalculator) -> None:
    """Test that decorated methods are properly discovered."""
    # Check tools
    tools = simple_calculator._tools
    assert "add" in tools
    assert "subtract" in tools
    assert tools["add"]["metadata"]["description"] == "Add two numbers"

    # Check prompts
    prompts = simple_calculator._prompts
    assert "math_question" in prompts
    assert prompts["math_question"]["metadata"]["description"] == "Generate a math question"

    # Check resources
    resources = simple_calculator._resources
    assert "/data.json" in resources
    assert resources["/data.json"]["metadata"]["mime_type"] == "application/json"


@pytest.mark.asyncio
async def test_mcp_tool_execution() -> None:
    """Test that MCP tools can be executed directly."""
    # Create an agent
    agent = BasicCalculator(name="calculator")

    # Call tools directly
    add_result = await agent.add(a=5, b=3)
    assert add_result["result"] == 8

    subtract_result = await agent.subtract(a=10, b=4)
    assert subtract_result["result"] == 6


@pytest.mark.asyncio
async def test_mcp_prompt_generation() -> None:
    """Test that MCP prompts can generate text."""
    # Create an agent
    agent = BasicCalculator(name="calculator")

    # Generate prompt
    prompt = await agent.math_question(difficulty="medium", topic="addition")
    assert "medium" in prompt
    assert "addition" in prompt
    assert "2+2" in prompt


@pytest.mark.asyncio
async def test_mcp_resource_retrieval() -> None:
    """Test that MCP resources can be retrieved."""
    # Create an agent
    agent = BasicCalculator(name="calculator")

    # Get resource
    resource_data = await agent.sample_data()
    assert isinstance(resource_data, bytes)

    # Parse JSON data
    data = json.loads(resource_data.decode("utf-8"))
    assert data["name"] == "Sample Data"
    assert data["values"] == [1, 2, 3, 4, 5]


class ComplexRequest(BaseModel):
    """Complex request model with nested structure."""

    operation: str = Field(..., description="Mathematical operation to perform")
    values: list = Field(..., description="List of values to operate on")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class ComplexResponse(BaseModel):
    """Complex response model with nested structure."""

    result: float = Field(..., description="Result of the operation")
    steps: int = Field(..., description="Number of steps taken")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class ComplexCalculator(McpAgent):
    """Calculator agent that uses Pydantic models for request/response."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the complex calculator.

        Args:
            **kwargs: Additional arguments for the parent class
        """
        name = kwargs.pop("name", "complex_calculator")
        super().__init__(
            config={
                "name": name,  # Ensure name is in the config
                "communicator_type": "mock",  # Use mock instead of 'none'
                "service_urls": {},  # Empty service URLs for testing
            },
            **kwargs,
        )

    @mcp_tool(
        name="compute",
        description="Perform a computation on a list of values",
        input_model=ComplexRequest,
        output_model=ComplexResponse,
    )
    async def compute(self, operation: str, values: list, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform a computation on a list of values.

        Args:
            operation: The operation to perform (sum, product, average)
            values: List of values to operate on
            metadata: Optional metadata

        Returns:
            Dictionary with computation results

        Raises:
            ValueError: If the operation is not supported
        """
        metadata = metadata or {}
        steps = len(values)

        if operation == "sum":
            result = sum(values)
        elif operation == "product":
            result = 1
            for val in values:
                result *= val
        elif operation == "average":
            result = sum(values) / len(values) if values else 0
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        return {"result": result, "steps": steps, "metadata": {**metadata, "operation": operation}}


@pytest.mark.asyncio
async def test_mcp_tool_with_pydantic_models() -> None:
    """Test MCP tool with complex Pydantic models."""
    # Create an agent
    agent = ComplexCalculator(name="complex_calculator")

    # Call the compute tool with different operations
    sum_result = await agent.compute(operation="sum", values=[1, 2, 3, 4, 5], metadata={"source": "test"})
    assert sum_result["result"] == 15
    assert sum_result["steps"] == 5
    assert sum_result["metadata"]["source"] == "test"

    product_result = await agent.compute(operation="product", values=[2, 3, 4], metadata={"precision": "high"})
    assert product_result["result"] == 24
    assert product_result["steps"] == 3
    assert product_result["metadata"]["precision"] == "high"

    # Test error handling
    with pytest.raises(ValueError) as excinfo:
        await agent.compute(operation="unsupported", values=[1, 2, 3])
    assert "Unsupported operation" in str(excinfo.value)
