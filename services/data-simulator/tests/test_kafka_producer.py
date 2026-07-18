import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.kafka_producer import KafkaClient

@pytest.fixture
def kafka_client():
    return KafkaClient()

@pytest.fixture(autouse=True)
def reset_kafka_client(kafka_client):
    """Ensure producer is reset after each test to prevent cross-test pollution."""
    yield
    kafka_client.producer = None

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
    
    mock_producer.start.assert_called_once()
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
        
    assert mock_sleep.call_count == 10

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
    
    mock_producer.send_and_wait.assert_called_once()
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
async def test_stop(kafka_client):
    """
    Test the shutdown process of the KafkaClient.
    Verifies that it invokes the stop mechanism on the underlying 
    AIOKafkaProducer to cleanly close the connection.
    """
    mock_producer = AsyncMock()
    kafka_client.producer = mock_producer
    
    await kafka_client.stop()
    
    mock_producer.stop.assert_called_once()

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
