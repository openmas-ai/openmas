"""Integration tests for MCP functionality using in-memory verification.

This file contains integration tests that verify the MCP decorators work
correctly without requiring network communication or subprocess execution.
"""

import json
from typing import Any, Dict

import pytest
from pydantic import BaseModel, Field

from openmas.agent import McpAgent, mcp_prompt, mcp_resource, mcp_tool

# Mark all tests in this module with the 'mcp' marker
pytestmark = pytest.mark.mcp


class SimpleCalculator(McpAgent):
    """Simple calculator agent that uses MCP decorators."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the calculator agent.

        Args:
            **kwargs: Additional arguments for the parent class
        """
        super().__init__(
            name="simple_calculator",
            config={
                "COMMUNICATOR_TYPE": "none",  # No communicator for this test
            },
            **kwargs,
        )

    @mcp_tool(
        name="add",
        description="Add two numbers together",
    )
    async def add_numbers(self, a: float, b: float) -> Dict[str, float]:
        """Add two numbers together.

        Args:
            a: First number
            b: Second number

        Returns:
            Dictionary with the result
        """
        return {"result": a + b}

    @mcp_tool(
        name="subtract",
        description="Subtract second number from first",
    )
    async def subtract_numbers(self, a: float, b: float) -> Dict[str, float]:
        """Subtract b from a.

        Args:
            a: First number
            b: Second number to subtract from first

        Returns:
            Dictionary with the result
        """
        return {"result": a - b}

    @mcp_prompt(
        name="math_question",
        description="Generate a math question",
    )
    async def generate_math_question(self, difficulty: str = "medium") -> str:
        """Generate a math question.

        Args:
            difficulty: The difficulty level (easy, medium, hard)

        Returns:
            A string with a math question
        """
        questions = {
            "easy": "What is 2 + 2?",
            "medium": "If x = 5 and y = 3, what is 2x - y?",
            "hard": "Solve for x: 3x² - 6x + 2 = 0",
        }
        return questions.get(difficulty.lower(), "What is 1 + 1?")

    @mcp_resource(
        uri="/sample.json",
        name="sample_data",
        description="Sample JSON data",
        mime_type="application/json",
    )
    async def get_sample_data(self) -> bytes:
        """Get sample JSON data.

        Returns:
            Sample data as UTF-8 encoded JSON bytes
        """
        data = {
            "numbers": [1, 2, 3, 4, 5],
            "operations": ["add", "subtract", "multiply", "divide"],
            "examples": {
                "add": {"a": 2, "b": 3, "result": 5},
                "subtract": {"a": 5, "b": 2, "result": 3},
            },
        }
        return json.dumps(data, indent=2).encode("utf-8")


class CalculationRequest(BaseModel):
    """Request model for calculation operations."""

    x: float = Field(..., description="First operand")
    y: float = Field(..., description="Second operand")


class CalculationResponse(BaseModel):
    """Response model for calculation operations."""

    result: float = Field(..., description="Calculation result")


class ComplexCalculator(McpAgent):
    """Calculator agent that uses Pydantic models for request/response."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the complex calculator.

        Args:
            **kwargs: Additional arguments for the parent class
        """
        super().__init__(
            name="complex_calculator",
            config={
                "COMMUNICATOR_TYPE": "none",  # No communicator for this test
            },
            **kwargs,
        )

    @mcp_tool(
        name="multiply",
        description="Multiply two numbers",
        input_model=CalculationRequest,
        output_model=CalculationResponse,
    )
    async def multiply(self, x: float, y: float) -> Dict[str, float]:
        """Multiply two numbers.

        Args:
            x: First number
            y: Second number

        Returns:
            Dictionary with the result
        """
        return {"result": x * y}

    @mcp_tool(
        name="divide",
        description="Divide first number by second",
        input_model=CalculationRequest,
        output_model=CalculationResponse,
    )
    async def divide(self, x: float, y: float) -> Dict[str, float]:
        """Divide x by y.

        Args:
            x: Numerator
            y: Denominator

        Returns:
            Dictionary with the result

        Raises:
            ValueError: If y is zero
        """
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return {"result": x / y}


@pytest.fixture
def simple_calculator() -> SimpleCalculator:
    """Create a simple calculator instance."""
    return SimpleCalculator()


@pytest.fixture
def complex_calculator() -> ComplexCalculator:
    """Create a complex calculator instance."""
    return ComplexCalculator()


@pytest.mark.asyncio
async def test_decorators_discovery(simple_calculator: SimpleCalculator) -> None:
    """Test that decorated methods are properly discovered."""
    # Check tools
    tools = simple_calculator._tools
    assert "add" in tools
    assert "subtract" in tools
    assert tools["add"]["metadata"]["description"] == "Add two numbers together"

    # Check prompts
    prompts = simple_calculator._prompts
    assert "math_question" in prompts
    assert prompts["math_question"]["metadata"]["description"] == "Generate a math question"

    # Check resources
    resources = simple_calculator._resources
    assert "/sample.json" in resources
    assert resources["/sample.json"]["metadata"]["mime_type"] == "application/json"


@pytest.mark.asyncio
async def test_tool_execution(simple_calculator: SimpleCalculator) -> None:
    """Test tool methods execution directly."""
    # Test add tool
    add_result = await simple_calculator.add_numbers(a=3.5, b=1.5)
    assert add_result["result"] == 5.0

    # Test subtract tool
    subtract_result = await simple_calculator.subtract_numbers(a=10, b=4)
    assert subtract_result["result"] == 6.0


@pytest.mark.asyncio
async def test_prompt_generation(simple_calculator: SimpleCalculator) -> None:
    """Test prompt generation methods directly."""
    # Generate an easy question
    easy_question = await simple_calculator.generate_math_question(difficulty="easy")
    assert easy_question == "What is 2 + 2?"

    # Generate a medium question
    medium_question = await simple_calculator.generate_math_question(difficulty="medium")
    assert "x = 5" in medium_question

    # Generate a hard question
    hard_question = await simple_calculator.generate_math_question(difficulty="hard")
    assert "3x²" in hard_question


@pytest.mark.asyncio
async def test_resource_retrieval(simple_calculator: SimpleCalculator) -> None:
    """Test resource retrieval methods directly."""
    # Get sample data
    sample_data_bytes = await simple_calculator.get_sample_data()
    sample_data = json.loads(sample_data_bytes.decode("utf-8"))

    # Verify contents
    assert "numbers" in sample_data
    assert "operations" in sample_data
    assert "examples" in sample_data
    assert sample_data["numbers"] == [1, 2, 3, 4, 5]
    assert "add" in sample_data["operations"]
    assert sample_data["examples"]["add"]["result"] == 5


@pytest.mark.asyncio
async def test_tool_with_pydantic_models(complex_calculator: ComplexCalculator) -> None:
    """Test tools that use Pydantic models for input/output."""
    # Test multiply
    multiply_result = await complex_calculator.multiply(x=4, y=5)
    assert multiply_result["result"] == 20

    # Test divide
    divide_result = await complex_calculator.divide(x=10, y=2)
    assert divide_result["result"] == 5.0

    # Test division by zero
    with pytest.raises(ValueError) as excinfo:
        await complex_calculator.divide(x=10, y=0)
    assert "Cannot divide by zero" in str(excinfo.value)
