from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, Optional

from backend.api.modules.preview_convergence.schemas.prototype import PrototypePreviewResponse


class PrototypePageGeneratorPort(ABC):
    @abstractmethod
    async def generate_pages(self, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate prototype pages based on targets."""
        pass

    @abstractmethod
    def preview_source(self) -> str:
        """Get the source identifier of this preview generator."""
        pass


class PrototypeGenerationServicePort(Protocol):
    async def generate_preview(
        self,
        project_id: int,
        force_regenerate: bool = False,
    ) -> PrototypePreviewResponse:
        ...

    async def get_latest_preview(
        self,
        project_id: int,
        session,
        raise_if_missing: bool = True,
    ) -> Optional[PrototypePreviewResponse]:
        ...


_page_generator: PrototypePageGeneratorPort | None = None
_prototype_generation_service: PrototypeGenerationServicePort | None = None


def get_page_generator() -> PrototypePageGeneratorPort | None:
    return _page_generator


def set_page_generator(generator: PrototypePageGeneratorPort) -> None:
    global _page_generator
    _page_generator = generator


def get_prototype_generation_service() -> PrototypeGenerationServicePort:
    if _prototype_generation_service is None:
        raise ValueError("PrototypeGenerationService has not been registered in ports.")
    return _prototype_generation_service


def set_prototype_generation_service(service: PrototypeGenerationServicePort) -> None:
    global _prototype_generation_service
    _prototype_generation_service = service
