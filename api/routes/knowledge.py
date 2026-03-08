"""Knowledge source API: fetch document content by filename."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pageindex import PageIndexAPIError

from api.responses import error, success

router = APIRouter(prefix="/api/v1", tags=["knowledge"])
logger = logging.getLogger(__name__)


@router.get("/knowledge/source")
async def get_knowledge_source(file: str | None = None):
    """Get knowledge base document content by filename.

    Filename must match the `name` field from list_pageindex_documents exactly.
    Returns OCR content (markdown) for frontend display.

    Query params:
        file: Document filename (required). Example: Guides_ASEAN 6 wide.pdf
    """
    if not file or not file.strip():
        return error(400, "Missing required parameter: file", status_code=400)

    from agent.research.pageindex_cache import pageindex_cache

    if not pageindex_cache.client:
        return error(503, "Knowledge base not available", status_code=503)

    doc_id = pageindex_cache.find_doc_id_by_filename(file.strip())
    if not doc_id:
        return error(404, f"Document not found: {file}", status_code=404)

    try:
        content = pageindex_cache.get_page_content(doc_id)
    except PageIndexAPIError as e:
        logger.exception("PageIndex API error fetching document %s", doc_id)
        return error(502, "Failed to fetch document content from PageIndex", status_code=502)
    except Exception as e:
        logger.exception("Unexpected error fetching knowledge source: %s", e)
        return error(502, "Failed to fetch document content from PageIndex", status_code=502)

    if content.get("status") != "completed":
        logger.warning("Document %s status=%s, returning partial content", doc_id, content.get("status"))

    doc = next(
        (d for d in pageindex_cache.documents if (d.get("id") or d.get("doc_id")) == doc_id),
        {},
    )
    doc_name = doc.get("name") or file.strip()

    return success({
        "doc_id": doc_id,
        "doc_name": doc_name,
        "pages": content.get("pages", []),
        "total_pages": content.get("total_pages", 0),
    })
