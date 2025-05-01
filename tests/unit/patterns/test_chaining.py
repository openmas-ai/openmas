"""Tests for src/openmas/patterns/chaining.py."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from openmas.patterns.chaining import ChainStep, ChainStepStatus, ServiceChain

# --- Test Fixtures ---


@pytest.fixture
def mock_communicator():
    """Provides a mock communicator with an async send_request."""
    comm = MagicMock()
    comm.send_request = AsyncMock()
    return comm


@pytest.fixture
def service_chain(mock_communicator):
    """Provides a ServiceChain instance with the mock communicator."""
    return ServiceChain(communicator=mock_communicator, name="test_chain")


# --- Test Cases for ServiceChain._execute_step ---


@pytest.mark.asyncio
async def test_execute_step_skipped_by_condition(service_chain, mock_communicator):
    """Test that a step is skipped if its condition function returns False."""
    step = ChainStep(
        target_service="service1", method="method1", name="step1", condition=lambda ctx: False  # Condition always false
    )
    context: dict[str, object] = {}

    result = await service_chain._execute_step(step, context)

    assert result.status == ChainStepStatus.SKIPPED
    assert result.result is None
    assert result.error is None
    assert result.attempt_count == 0  # Should not attempt if skipped
    mock_communicator.send_request.assert_not_called()


@pytest.mark.asyncio
async def test_execute_step_retry_failure(service_chain, mock_communicator):
    """Test that a step fails after exhausting retries."""
    mock_communicator.send_request.side_effect = ValueError("Service Unavailable")
    step = ChainStep(
        target_service="service1",
        method="method1",
        name="step1",
        retry_count=2,  # Try initial + 2 retries = 3 attempts
        retry_delay=0.01,  # Short delay for testing
    )
    context: dict[str, object] = {}

    # Patch asyncio.sleep to avoid actual sleeping
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await service_chain._execute_step(step, context)

    assert result.status == ChainStepStatus.FAILURE
    assert result.result is None
    assert "Service Unavailable" in result.error  # Check only the message part
    assert result.attempt_count == 3  # Initial call + 2 retries
    # Check send_request was called 3 times
    assert mock_communicator.send_request.call_count == 3
    expected_calls = [
        call(target_service="service1", method="method1", params={}, timeout=None),
        call(target_service="service1", method="method1", params={}, timeout=None),
        call(target_service="service1", method="method1", params={}, timeout=None),
    ]
    mock_communicator.send_request.assert_has_calls(expected_calls)
    # Check sleep was called twice (between attempts)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_has_calls([call(0.01), call(0.01)])


@pytest.mark.asyncio
async def test_execute_step_error_handler_recovers(service_chain, mock_communicator):
    """Test that an error handler can recover from an error and return a value."""
    original_exception = ValueError("Temporary Glitch")
    recovery_value = {"recovered": True, "data": "default"}

    # Mock send_request to raise an error
    mock_communicator.send_request.side_effect = original_exception

    # Define an error handler that returns a default value
    def simple_error_handler(exception, context):
        assert exception is original_exception
        assert isinstance(context, dict)
        # Log or inspect error
        return recovery_value

    step = ChainStep(target_service="service1", method="method1", name="step1", error_handler=simple_error_handler)
    context: dict[str, object] = {}

    result = await service_chain._execute_step(step, context)

    assert result.status == ChainStepStatus.SUCCESS  # Recovered
    assert result.result == recovery_value
    assert result.error is None  # Error was handled
    assert result.attempt_count == 1  # Should succeed on first attempt via handler
    mock_communicator.send_request.assert_called_once()  # Ensure request was attempted


@pytest.mark.asyncio
async def test_execute_step_transform_output(service_chain, mock_communicator):
    """Test that transform_output modifies the successful result."""
    original_result = {"raw_data": 123}
    transformed_result = {"processed_data": 123}

    # Mock send_request to return a successful result
    mock_communicator.send_request.return_value = original_result

    # Define a transform function
    def simple_transformer(output):
        assert output == original_result
        return transformed_result

    step = ChainStep(target_service="service1", method="method1", name="step1", transform_output=simple_transformer)
    context: dict[str, object] = {}

    result = await service_chain._execute_step(step, context)

    assert result.status == ChainStepStatus.SUCCESS
    assert result.result == transformed_result  # Should be the transformed result
    assert result.error is None
    assert result.attempt_count == 1
    mock_communicator.send_request.assert_called_once()


# --- Test Cases for ServiceChain._prepare_parameters ---


def test_prepare_parameters_no_transform(service_chain):
    """Test parameter preparation without any transformation or context."""
    step = ChainStep(target_service="s1", method="m1", parameters={"p1": "v1", "p2": 123})
    context: dict[str, object] = {"other_data": "ignore"}

    prepared_params = service_chain._prepare_parameters(step, context)

    assert prepared_params == {"p1": "v1", "p2": 123}


def test_prepare_parameters_with_transform(service_chain):
    """Test parameter preparation with an input transformation function."""

    def input_transformer(context):
        assert "prev_step_result" in context
        return {"input": context["prev_step_result"], "extra": True}

    step = ChainStep(
        target_service="s1",
        method="m1",
        parameters={"initial": "value"},  # Initial params are ignored if transform_input exists
        transform_input=input_transformer,
    )
    context: dict[str, object] = {"prev_step_result": "data_from_prev"}

    prepared_params = service_chain._prepare_parameters(step, context)

    assert prepared_params == {"input": "data_from_prev", "extra": True}


def test_prepare_parameters_transform_overrides_defaults(service_chain):
    """Test that transform_input completely replaces default parameters."""

    def input_transformer(context):
        return {"transformed": True}

    step = ChainStep(
        target_service="s1",
        method="m1",
        parameters={"initial": "value"},  # Should be ignored
        transform_input=input_transformer,
    )
    context: dict[str, object] = {}

    prepared_params = service_chain._prepare_parameters(step, context)

    assert prepared_params == {"transformed": True}
    assert "initial" not in prepared_params
