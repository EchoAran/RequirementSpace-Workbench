"""Binary/Base64 conversion utilities.

This module keeps binary storage concerns separate from JSON/API transport concerns.
It is suitable for converting SQLite BLOB bytes to base64 strings and back.
"""

from __future__ import annotations

import base64
import binascii
from typing import Union

BytesLike = Union[bytes, bytearray, memoryview]


class BinaryConversionError(ValueError):
    """Raised when base64 text cannot be decoded into bytes."""


class BinaryConversionService:
    """Convert bytes and base64 strings.

    Methods return plain base64 text without a data URL prefix by default.
    """

    @staticmethod
    def bytes_to_base64(data: BytesLike, *, urlsafe: bool = False) -> str:
        """Convert bytes-like data to a base64 string.

        Args:
            data: bytes, bytearray, or memoryview.
            urlsafe: Use URL-safe base64 alphabet when True.

        Returns:
            UTF-8 base64 string.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes, bytearray, or memoryview")

        raw = bytes(data)
        encoded = (
            base64.urlsafe_b64encode(raw)
            if urlsafe
            else base64.b64encode(raw)
        )
        return encoded.decode("utf-8")

    @staticmethod
    def base64_to_bytes(data: str, *, urlsafe: bool = False) -> bytes:
        """Convert a base64 string to bytes.

        Args:
            data: Base64 string. Data URL prefixes such as
                'data:image/png;base64,' are accepted.
            urlsafe: Use URL-safe base64 alphabet when True.

        Returns:
            Decoded bytes.

        Raises:
            BinaryConversionError: Invalid base64 content.
        """
        if not isinstance(data, str):
            raise TypeError("data must be str")

        cleaned = data.strip()
        if "," in cleaned and cleaned.lower().startswith("data:"):
            cleaned = cleaned.split(",", 1)[1]

        cleaned = "".join(cleaned.split())

        # Add missing padding for inputs produced by some clients.
        padding = (-len(cleaned)) % 4
        if padding:
            cleaned += "=" * padding

        try:
            decoder = base64.urlsafe_b64decode if urlsafe else base64.b64decode
            return decoder(cleaned, validate=not urlsafe)
        except (binascii.Error, ValueError) as exc:
            raise BinaryConversionError("invalid base64 data") from exc


# Convenience functions for direct import style.
def bytes_to_base64(data: BytesLike, *, urlsafe: bool = False) -> str:
    return BinaryConversionService.bytes_to_base64(data, urlsafe=urlsafe)


def base64_to_bytes(data: str, *, urlsafe: bool = False) -> bytes:
    return BinaryConversionService.base64_to_bytes(data, urlsafe=urlsafe)


if __name__ == "__main__":

    raw = b"hello"

    encoded = bytes_to_base64(raw)
    print(encoded)

    decoded = base64_to_bytes(encoded)
    print(decoded)

    assert decoded == raw
