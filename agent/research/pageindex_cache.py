"""PageIndex cache and client management.

This module provides a singleton cache for PageIndex document metadata
and a client wrapper for the PageIndex API.
"""

import logging
import os
import threading
import time
from typing import Dict, List, Optional

from pageindex import PageIndexClient, PageIndexAPIError

logger = logging.getLogger(__name__)

# Retry config for 504 Gateway Timeout (common when many parallel queries hit PageIndex)
PAGEINDEX_RETRY_COUNT = 3
PAGEINDEX_RETRY_DELAY_SEC = 1.0

# Request counter for correlating parallel requests (thread-safe)
_request_counter = 0
_request_lock = threading.Lock()


class PageIndexCache:
    """Singleton cache for PageIndex documents and API client."""

    _instance = None

    def __new__(cls):
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the PageIndex client and cache."""
        if self._initialized:
            return

        api_key = os.getenv("PAGEINDEX_API_KEY")
        if not api_key:
            logger.warning("PAGEINDEX_API_KEY not found in environment")
            self.client = None
            self.documents = []
        else:
            self.client = PageIndexClient(api_key=api_key)
            self.documents: List[Dict] = []
            self._load_documents()

        self._initialized = True

    def _load_documents(self):
        """Load all documents from PageIndex into cache."""
        if not self.client:
            return

        try:
            response = self.client.list_documents()
            self.documents = response.get("documents", [])
            logger.info(f"✅ Loaded {len(self.documents)} PageIndex documents into cache")
        except Exception as e:
            logger.error(f"❌ Failed to load PageIndex documents: {e}")
            self.documents = []

    def find_doc_id_by_filename(self, filename: str) -> Optional[str]:
        """Find doc_id in cache by filename (exact match, case-insensitive).

        Args:
            filename: Document name to look up (must match list_documents name).

        Returns:
            doc_id or None if not found.
        """
        if not filename or not self.documents:
            return None
        target = filename.strip().lower()
        for doc in self.documents:
            name = (doc.get("name") or "").strip().lower()
            if name == target:
                return doc.get("id") or doc.get("doc_id")
        return None

    def get_page_content(self, doc_id: str) -> dict:
        """Get full OCR content of a document via PageIndex API.

        Args:
            doc_id: PageIndex document ID.

        Returns:
            {"pages": [...], "total_pages": int, "status": str}
            Each page: {page_index (1-based), markdown, images}.

        Raises:
            PageIndexAPIError or other on API failure.
        """
        if not self.client:
            return {"pages": [], "total_pages": 0, "status": "unavailable"}
        response = self.client.get_ocr(doc_id, format="page")
        status = response.get("status", "unknown")
        result = response.get("result") or []
        if status != "completed":
            logger.warning(f"Document {doc_id} status={status}, result may be empty")
        pages = []
        for item in result:
            pages.append({
                "page_index": item.get("page_index", 0),
                "markdown": item.get("markdown", ""),
                "images": item.get("images") or [],
            })
        return {
            "pages": pages,
            "total_pages": len(pages),
            "status": status,
        }

    def get_document_list(self) -> str:
        """Return formatted document list for LLM consumption.

        Returns:
            Formatted string listing all available documents with metadata.
        """
        if not self.documents:
            return "No PageIndex documents available in the knowledge base."

        result = "Available PageIndex Knowledge Base Documents (id | name | description):\n\n"
        for doc in self.documents:
            # API returns "id" (list_documents), "doc_id" used elsewhere
            doc_id = doc.get("id") or doc.get("doc_id") or "unknown"
            name = doc.get("name", "Untitled")
            description = doc.get("description", "No description available")
            result += f"**{doc_id}**: {name}\n{description}\n\n"
        return result

    def query(self, query: str, doc_ids: Optional[List[str]] = None) -> str:
        """Query PageIndex using the Chat API.

        Includes retry logic for 504 Gateway Timeout, which can occur when
        many parallel queries hit PageIndex simultaneously.
        """
        if not self.client:
            return "Error: PageIndex client not initialized. Please check PAGEINDEX_API_KEY."

        # Assign request ID for log correlation (parallel requests have close IDs)
        with _request_lock:
            global _request_counter
            _request_counter += 1
            req_id = _request_counter

        started_at = time.monotonic()
        query_preview = (query[:80] + "…") if len(query) > 80 else query
        doc_ids_str = str(doc_ids) if doc_ids else "all"

        logger.info(
            "[PageIndex] req_id=%d START query=%r doc_ids=%s",
            req_id,
            query_preview,
            doc_ids_str,
        )

        last_error = None
        for attempt in range(PAGEINDEX_RETRY_COUNT):
            try:
                response = self.client.chat_completions(
                    messages=[{"role": "user", "content": query}],
                    doc_id=doc_ids,
                    enable_citations=True,  # Request citations in response
                )
                content = response["choices"][0]["message"]["content"]
                elapsed_ms = (time.monotonic() - started_at) * 1000
                logger.info(
                    "[PageIndex] req_id=%d OK elapsed_ms=%.0f response_len=%d",
                    req_id,
                    elapsed_ms,
                    len(content),
                )
                # Log PageIndex return content (preview) for debugging
                preview_len = 800
                preview = (content[:preview_len] + "…") if len(content) > preview_len else content
                logger.info("[PageIndex] req_id=%d RESPONSE preview:\n%s", req_id, preview)
                return content
            except PageIndexAPIError as e:
                last_error = e
                err_msg = str(e)
                err_preview = err_msg[:200] + "…" if len(err_msg) > 200 else err_msg
                err_lower = err_msg.lower()
                is_504 = (
                    "504" in err_lower
                    or "gateway time-out" in err_lower
                    or "gateway timeout" in err_lower
                    or "timeout" in err_lower
                )
                logger.warning(
                    "[PageIndex] req_id=%d attempt=%d/%d error=%s",
                    req_id,
                    attempt + 1,
                    PAGEINDEX_RETRY_COUNT,
                    err_preview,
                )
                if is_504 and attempt < PAGEINDEX_RETRY_COUNT - 1:
                    delay = PAGEINDEX_RETRY_DELAY_SEC * (attempt + 1)
                    logger.info(
                        "[PageIndex] req_id=%d retrying in %.1fs (504 detected)",
                        req_id,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "[PageIndex] req_id=%d FAILED after %d attempts: %s",
                        req_id,
                        attempt + 1,
                        err_preview,
                    )
                    return f"Error querying PageIndex: {str(e)}"
            except Exception as e:
                elapsed_ms = (time.monotonic() - started_at) * 1000
                logger.error(
                    "[PageIndex] req_id=%d FAILED elapsed_ms=%.0f error=%s",
                    req_id,
                    elapsed_ms,
                    str(e),
                )
                return f"Error querying PageIndex: {str(e)}"

        elapsed_ms = (time.monotonic() - started_at) * 1000
        logger.error(
            "[PageIndex] req_id=%d FAILED after %d retries elapsed_ms=%.0f: %s",
            req_id,
            PAGEINDEX_RETRY_COUNT,
            elapsed_ms,
            str(last_error),
        )
        return f"Error querying PageIndex: {str(last_error)}"


# Global singleton instance
pageindex_cache = PageIndexCache()

