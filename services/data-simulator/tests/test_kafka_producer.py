import pytest
import logging
from unittest.mock import patch, AsyncMock
from src.kafka_producer import KafkaClient

# Each test builds a fresh KafkaClient via the fixture below; because the
# instance is function-scoped there is no cross-test state to reset (the
# module-level singleton `kafka_client` in src.kafka_producer is never touched).
@pytest.fixture
def kafka_client():
    return KafkaClient()

@pytest.mark.asyncio
@patch('src.kafka_producer.AIOKafkaProducer')
async def test_start_success(mock_producer_class, kafka_client):
    """
    Test the successful startup of the KafkaClient.
    Verifies that it initializes the underlying AIOKafkaProducer and 
    successfully connects to the broker without raising exceptions.
    """
    mock_producer = AsyncMock()
    mock_producer_class.return_value = mock_producer
    
    await kafka_client.start()

    mock_producer.start.assert_awaited_once()
    assert kafka_client.producer == mock_producer

@pytest.mark.asyncio
@patch('src.kafka_producer.asyncio.sleep')
@patch('src.kafka_producer.AIOKafkaProducer')
async def test_start_retry_and_fail(mock_producer_class, mock_sleep, kafka_client):
    """
    Test the resilient retry logic of the KafkaClient startup process.
    Simulates repeated connection failures to ensure the client attempts
    to reconnect a maximum number of times before ultimately raising an error.
    """
    mock_producer_class.side_effect = Exception("Connection failed")

    with pytest.raises(Exception, match="Could not connect to Kafka"):
        await kafka_client.start()

    # The producer constructor is attempted exactly `retries` (10) times —
    # this is the real retry contract.
    assert mock_producer_class.call_count == 10
    # Sleep happens between retries. The current implementation also sleeps
    # after the final failure before raising (so 10, not 9); we assert `>= 9`
    # so the test does not lock in that trailing-sleep detail if the loop is
    # later changed to skip sleeping after the last attempt.
    assert mock_sleep.call_count >= 9

@pytest.mark.asyncio
@patch('src.kafka_producer.asyncio.sleep')
@patch('src.kafka_producer.AIOKafkaProducer')
async def test_start_retry_then_success(mock_producer_class, mock_sleep, kafka_client):
    """
    Test that a transient failure on the first attempt is retried and then
    succeeds on the second attempt. Also verifies the partially-constructed
    producer from the failed attempt is cleaned up via producer.stop().
    """
    mock_producer_1 = AsyncMock()
    mock_producer_1.start.side_effect = Exception("Broker not ready")
    # Cleanup of the failed producer also failing should be swallowed, not raised
    mock_producer_1.stop.side_effect = Exception("Cleanup failed")
    mock_producer_2 = AsyncMock()
    mock_producer_class.side_effect = [mock_producer_1, mock_producer_2]

    await kafka_client.start()

    # First attempt failed -> its producer was cleaned up (even though cleanup errored)
    mock_producer_1.start.assert_awaited_once()
    mock_producer_1.stop.assert_awaited_once()
    # Second attempt succeeded -> became the active producer
    mock_producer_2.start.assert_awaited_once()
    assert kafka_client.producer is mock_producer_2
    # Only one sleep between the two attempts
    assert mock_sleep.call_count == 1

@pytest.mark.asyncio
@patch('src.kafka_producer.settings')
async def test_send_telemetry_success(mock_settings, kafka_client):
    """
    Test successfully transmitting telemetry data through the KafkaClient.
    Verifies that payloads are correctly encoded and dispatched to the
    appropriately configured Kafka topic.
    """
    mock_settings.KAFKA_TOPIC = "test_topic"
    
    mock_producer = AsyncMock()
    kafka_client.producer = mock_producer
    
    payload = {"key": "value"}
    await kafka_client.send_telemetry("bin_1", payload)

    mock_producer.send_and_wait.assert_awaited_once()
    args, kwargs = mock_producer.send_and_wait.call_args
    assert kwargs['topic'] == 'test_topic'
    assert kwargs['value'] == payload
    assert kwargs['key'] == b'bin_1'

@pytest.mark.asyncio
async def test_send_telemetry_not_started(kafka_client, caplog):
    """
    Test sending telemetry when the KafkaClient has not been started.
    Ensures that it fails gracefully, dropping the message and logging 
    an error rather than crashing the application.
    """
    await kafka_client.send_telemetry("bin_1", {})
    assert "Kafka producer is not started" in caplog.text

@pytest.mark.asyncio
async def test_stop(kafka_client, caplog):
    """
    Test the shutdown process of the KafkaClient.
    Verifies that it invokes the stop mechanism on the underlying 
    AIOKafkaProducer to cleanly close the connection and logs shutdown.
    """
    caplog.set_level(logging.INFO)
    mock_producer = AsyncMock()
    kafka_client.producer = mock_producer
    
    await kafka_client.stop()

    mock_producer.stop.assert_awaited_once()
    assert "Kafka producer stopped" in caplog.text

@pytest.mark.asyncio
async def test_stop_when_producer_is_none(kafka_client, caplog):
    """
    Test stopping the KafkaClient when no producer was ever started.
    Ensures it does not crash and still logs the shutdown message.
    """
    caplog.set_level(logging.INFO)
    kafka_client.producer = None

    await kafka_client.stop()

    assert kafka_client.producer is None
    assert "Kafka producer stopped" in caplog.text

@pytest.mark.asyncio
async def test_send_telemetry_exception_handled(kafka_client, caplog):
    """
    Test that exceptions raised during send_and_wait are caught and logged,
    rather than crashing the application.
    """
    mock_producer = AsyncMock()
    mock_producer.send_and_wait.side_effect = Exception("Kafka timeout")
    kafka_client.producer = mock_producer
    
    # Should not raise an exception
    await kafka_client.send_telemetry("bin_1", {})
    
    assert "Failed to send telemetry for bin_1" in caplog.text
