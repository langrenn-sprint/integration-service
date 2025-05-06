"""Module for google pub/sub adapter."""

import json
import logging
import os

from google.api_core import retry
from google.cloud import pubsub_v1  # type: ignore[attr-defined]


class GooglePubSubAdapter:
    """Class representing google pub sub adapter."""

    def publish_message(self, data_str: str) -> str:
        """Get all items for an album."""
        servicename = "GooglePubSubAdapter.publish_message"
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        topic_id = os.getenv("GOOGLE_PUBSUB_TOPIC_ID", "")
        if project_id == "":
            err_msg = "GOOGLE_CLOUD_PROJECT not found in .env"
            raise Exception(err_msg)
        if topic_id == "":
            err_msg = "GOOGLE_PUBSUB_TOPIC_ID not found in .env"
            raise Exception(err_msg)

        try:
            publisher = pubsub_v1.PublisherClient()
            # The `topic_path` method creates a fully qualified identifier
            # in the form `projects/{project_id}/topics/{topic_id}`
            topic_path = publisher.topic_path(project_id, topic_id)

            # Data must be a bytestring
            data = data_str.encode("utf-8")
            # When you publish a message, the client returns a future.
            future = publisher.publish(topic_path, data)
        except Exception as e:
            error_text = f"{servicename}, data: {data_str}."
            logging.exception(error_text)
            raise Exception(error_text) from e
        return future.result()

    def pull_messages(self) -> list:
        """Pull messages from topic. Return messages as list of dicts."""
        servicename = "GooglePubSubAdapter.pull_messages"
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        subscription_id = os.getenv("GOOGLE_PUBSUB_SUBSCRIPTION_ID", "")
        num_messages = int(os.getenv("GOOGLE_PUBSUB_NUM_MESSAGES", "10"))
        if project_id == "":
            err_msg = "GOOGLE_CLOUD_PROJECT not found in .env"
            raise Exception(err_msg)
        if subscription_id == "":
            err_msg = "GOOGLE_PUBSUB_SUBSCRIPTION_ID not found in .env"
            raise Exception(err_msg)

        try:
            message_body = []
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(
                project_id, subscription_id
            )

            # Wrap the subscriber in a 'with' block to automatically call close() to
            # close the underlying gRPC channel when done.
            with subscriber:
                # The subscriber pulls a specific number of messages. The actual
                # number of messages pulled may be smaller than max_messages.
                response = subscriber.pull(
                    request={
                        "subscription": subscription_path,
                        "max_messages": num_messages,
                    },
                    retry=retry.Retry(deadline=300),
                )

                if len(response.received_messages) == 0:
                    return []

                ack_ids = []
                for received_message in response.received_messages:
                    message_json = received_message.message.data.decode("utf-8")
                    message_body.append(json.loads(message_json))
                    ack_ids.append(received_message.ack_id)

                # Acknowledges the received messages so they will not be sent again.
                subscriber.acknowledge(
                    request={"subscription": subscription_path, "ack_ids": ack_ids}
                )
        except Exception as e:
            logging.exception(servicename)
            raise Exception(servicename) from e

        return message_body
