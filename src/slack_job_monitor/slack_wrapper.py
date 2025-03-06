import getpass
import os
import platform
import time

from loguru import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class RateLimiter:
    def __init__(self, period_sec: float) -> None:
        self.period_sec = period_sec
        self.last_ok = 0.0

    def __call__(self) -> bool:
        now = time.time()
        if (now - self.last_ok) > self.period_sec:
            self.last_ok = now
            return True
        return False


class SlackClientWrapper:
    def __init__(self, target_channel: str = "webhooks", debug=False) -> None:
        self.slack_user_id = os.environ["SLACK_USER_ID"]
        self.slack_bot_token = os.environ["SLACK_BOT_TOKEN"]

        self.client = WebClient(token=self.slack_bot_token)
        self.channel_id: str | None = self._get_channel_id(target_channel)
        if self.channel_id is None:
            logger.error(
                f"Failed to find channel '{target_channel}'. No messages can be posted."
            )

        self.base_ts: str | None = self._post_base_message()
        if debug and self.base_ts is not None:
            self.ping_user(self.base_ts)

    def _get_channel_id(self, channel_name: str) -> str | None:
        try:
            for result in self.client.conversations_list():
                for channel in result["channels"]:
                    if channel["name"] == channel_name:
                        return channel["id"]
        except SlackApiError as e:
            logger.error(f"{e}")

        return None

    def _post_base_message(self) -> str | None:
        """
        Returns the ts of the base message, which functions as a message ID for
        updates and thread replies.
        """

        if self.channel_id is None:
            return None

        try:
            result = self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"{getpass.getuser()}@{platform.node()}:",
            )
            return result.data["ts"]  # type: ignore
        except SlackApiError as e:
            logger.error(f"{e}")

        return None

    def update_post(self, message: str) -> None:
        if self.channel_id is None or self.base_ts is None:
            return

        try:
            self.client.chat_update(
                channel=self.channel_id,
                ts=self.base_ts,
                text=message,
            )
        except SlackApiError as e:
            logger.error(f"{e}")

    def ping_user(self, message: str = "") -> None:
        if self.channel_id is None or self.base_ts is None:
            return

        try:
            self.client.chat_postMessage(
                channel=self.channel_id,
                thread_ts=self.base_ts,
                text=f"<@{self.slack_user_id}> {message}",
            )
        except SlackApiError as e:
            logger.error(f"{e}")
