"""Base module for gRPC communication components."""

import time


class Base:
    def close_channel(self) -> None:
        """Close the channel."""
        if self._channel is not None and not self._channel.is_closed():
            for callback in self._on_close_callbacks:
                callback()
            timeout = time.time() + 5
            while not self._channel.is_closed() and time.time() < timeout:
                time.sleep(0.1)
        else:
            self._logger.debug("Channel already closed or non-existent.")
