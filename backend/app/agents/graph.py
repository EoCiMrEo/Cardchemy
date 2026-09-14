"""Compatibility facade for the provider-neutral generation pipeline."""

from typing import Any

from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.ai.pipeline import FlashcardGenerationPipeline
from app.ai.providers import AIProvider
from app.config import Settings


class FlashcardGraph:
    """Retains the old ``ainvoke`` boundary without a framework dependency."""

    def __init__(self, settings: Settings | None = None, provider: AIProvider | None = None):
        self.pipeline = FlashcardGenerationPipeline(settings=settings, provider=provider)

    async def ainvoke(self, state: dict[str, Any], config: dict[str, Any] | None = None):
        del config
        document = state.get("pdf_document")
        if not isinstance(document, ExtractedDocument):
            legacy_text = state.get("pdf_text", "")
            document = ExtractedDocument(pages=[ExtractedPage(page_number=1, text=legacy_text)])
        return await self.pipeline.run(document, int(state.get("target_count", 20)))


def create_flashcard_graph(
    settings: Settings | None = None, provider: AIProvider | None = None
) -> FlashcardGraph:
    return FlashcardGraph(settings=settings, provider=provider)
