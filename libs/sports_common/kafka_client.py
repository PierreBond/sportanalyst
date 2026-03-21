from __future__ import annotations

import json
from typing import Any, Any

import structlog

from sports_common.config import settings
from sports_common.logging import get_logger

logger = get_logger(__name__)


def _get_kafka_modules() -> Any:
    """Lazily import kafka modules, raising a helpful error if absent."""
    try:
        from kafka import KafkaConsumer, KafkaProducer
        from kafka.admin import KafkaAdminClient, NewTopic
        from kafka.errors import TopicAlreadyExistsError

        return KafkaConsumer, KafkaProducer, KafkaAdminClient, NewTopic, TopicAlreadyExistsError
    except ImportError:
        raise RuntimeError(
            "kafka-python is required for KafkaClient. Install it with: pip install kafka-python"
        )


class JSONSerializer:
    @staticmethod
    def serialize(value: dict[str, Any]) -> bytes:
        return json.dumps(value).encode("utf-8")

    @staticmethod
    def deserialize(value: bytes) -> dict[str, Any]:
        return json.loads(value.decode("utf-8"))


class KafkaClient:
    def __init__(
        self,
        bootstrap_servers: str | None = None,
        consumer_group: str | None = None,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._consumer_group = consumer_group or settings.kafka_consumer_group
        self._producer: Any = None
        self._admin_client: Any = None

    @property
    def producer(self) -> Any:
        if self._producer is None:
            _, KafkaProducer, _, _, _ = _get_kafka_modules()
            self._producer = KafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                value_serializer=JSONSerializer.serialize,
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
            )
        return self._producer

    @property
    def admin_client(self) -> Any:
        if self._admin_client is None:
            _, _, KafkaAdminClient, _, _ = _get_kafka_modules()
            self._admin_client = KafkaAdminClient(
                bootstrap_servers=self._bootstrap_servers,
                client_id="sports-prediction-admin",
            )
        return self._admin_client

    def create_topics(self, topics: list[str], num_partitions: int = 3) -> None:
        _, _, _, NewTopic, TopicAlreadyExistsError = _get_kafka_modules()
        new_topics = []
        for topic in topics:
            new_topics.append(
                NewTopic(
                    name=topic,
                    num_partitions=num_partitions,
                    replication_factor=1,
                )
            )
        try:
            self.admin_client.create_topics(new_topics, validate_only=False)
            logger.info("topics_created", topics=topics)
        except TopicAlreadyExistsError:
            logger.info("topics_already_exist", topics=topics)

    def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> None:
        future = self.producer.send(topic, value=value, key=key)
        logger.debug(
            "message_sent",
            topic=topic,
            key=key,
            partition=future.partition,
            offset=future.offset,
        )

    def flush(self) -> None:
        self.producer.flush()

    def close(self) -> None:
        if self._producer:
            self._producer.close()
        if self._admin_client:
            self._admin_client.close()

    def __enter__(self) -> "KafkaClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class AsyncKafkaConsumer:
    def __init__(
        self,
        topics: list[str],
        bootstrap_servers: str | None = None,
        consumer_group: str | None = None,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._consumer_group = consumer_group or settings.kafka_consumer_group
        self._topics = topics
        self._consumer: Any = None

    def _get_consumer(self) -> Any:
        if self._consumer is None:
            KafkaConsumer, _, _, _, _ = _get_kafka_modules()
            self._consumer = KafkaConsumer(
                *self._topics,
                bootstrap_servers=self._bootstrap_servers,
                group_id=self._consumer_group,
                value_deserializer=JSONSerializer.deserialize,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                consumer_timeout_ms=1000,
            )
        return self._consumer

    def consume(self) -> Any:
        consumer = self._get_consumer()
        while True:
            try:
                for message in consumer:
                    yield {
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "key": message.key.decode("utf-8") if message.key else None,
                        "value": message.value,
                        "timestamp": message.timestamp,
                    }
            except StopIteration:
                break

    def close(self) -> None:
        if self._consumer:
            self._consumer.close()

    async def consume_messages(
        self,
        handler: Any,
    ) -> None:
        for message in self.consume():
            try:
                await handler(message)
            except Exception as e:
                logger.error("message_handler_error", error=str(e), message=message)


class KafkaProducerWrapper:
    def __init__(
        self,
        bootstrap_servers: str | None = None,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer: Any = None

    @property
    def producer(self) -> Any:
        if self._producer is None:
            _, KafkaProducer, _, _, _ = _get_kafka_modules()
            self._producer = KafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                value_serializer=JSONSerializer.serialize,
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
            )
        return self._producer

    def publish(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> None:
        future = self.producer.send(topic, value=value, key=key)
        logger.info(
            "published_to_kafka",
            topic=topic,
            key=key,
            partition=future.partition,
            offset=future.offset,
        )

    def flush(self) -> None:
        self.producer.flush()

    def close(self) -> None:
        if self._producer:
            self._producer.close()
