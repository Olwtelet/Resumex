"""The contract every content source implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from resumex.models import Story


class Source(ABC):
    """Yields :class:`~resumex.models.Story` objects from somewhere."""

    name: str = "source"

    @abstractmethod
    def stories(self) -> Iterator[Story]:
        """Yield stories, newest or best first where that concept applies."""

    def __iter__(self) -> Iterator[Story]:
        return self.stories()
