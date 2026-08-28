"""Chat completions via the Mistral API.

Two shapes cover every use in the pipeline: free text for generated answers,
and a parsed Pydantic model for the steps whose output is consumed by code
rather than read by a person — intent detection, reranking, evidence checks.
"""

from typing import List, Optional, Type, TypeVar, Union

from mistralai.client.models import (
    AssistantMessageTypedDict,
    SystemMessageTypedDict,
    ToolMessageTypedDict,
    UserMessageTypedDict,
)
from pydantic import BaseModel

from ..config.settings import get_settings
from ..logging import get_logger
from .client import get_client

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class ChatError(RuntimeError):
    """Raised when the API returns no usable content."""


# The SDK types `messages` as a list of the full union; a narrower list type
# will not satisfy it, because list is invariant in its element type.
Message = Union[
    SystemMessageTypedDict,
    UserMessageTypedDict,
    AssistantMessageTypedDict,
    ToolMessageTypedDict,
]


def _messages(user: str, system: Optional[str]) -> List[Message]:
    messages: List[Message] = []
    if system:
        messages.append(SystemMessageTypedDict(role="system", content=system))
    messages.append(UserMessageTypedDict(role="user", content=user))
    return messages


class MistralChat:
    """Thin wrapper over chat completions.

    Temperature defaults to 0: every call in this pipeline is a decision the
    system has to make consistently, not prose that benefits from variety.
    """

    def __init__(self) -> None:
        self.model = get_settings().MISTRAL_CHAT_MODEL

    async def complete(
        self,
        user: str,
        system: Optional[str] = None,
        *,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """Return the model's reply as text.

        Raises:
            ChatError: if the response carries no text.
        """
        response = await get_client().chat.complete_async(
            model=model or self.model,
            messages=_messages(user, system),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.choices or response.choices[0].message is None:
            raise ChatError("Chat response contained no message")

        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ChatError("Chat response contained no text")

        return content

    async def parse(
        self,
        user: str,
        schema: Type[T],
        system: Optional[str] = None,
        *,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> T:
        """Return the model's reply parsed into `schema`.

        Uses Mistral's structured output, so the schema is enforced server-side
        rather than by parsing whatever JSON came back.

        Raises:
            ChatError: if the response could not be parsed into the schema.
        """
        response = await get_client().chat.parse_async(
            model=model or self.model,
            messages=_messages(user, system),
            response_format=schema,
            temperature=temperature,
        )

        if not response.choices or response.choices[0].message is None:
            raise ChatError("Chat response contained no message")

        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ChatError(f"Chat response could not be parsed into {schema.__name__}")

        return parsed


_chat: Optional[MistralChat] = None


def get_chat() -> MistralChat:
    """Return the process-wide chat wrapper."""
    global _chat
    if _chat is None:
        _chat = MistralChat()
    return _chat
