"""Research Tools.

This module provides search and content processing utilities for the research agent,
using PageIndex for knowledge retrieval and Tavily for web search (currently disabled).
"""

import os
from typing import List, Optional

import httpx
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated, Literal

from agent.research.pageindex_cache import pageindex_cache

# Initialize Tavily client only if API key is available (currently disabled)
tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 1)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Formatted search results with full webpage content
    """
    # Use Tavily to discover URLs
    search_results = tavily_client.search(
        query,
        max_results=max_results,
        topic=topic,
    )

    # Fetch full content for each URL
    result_texts = []
    for result in search_results.get("results", []):
        url = result["url"]
        title = result["title"]

        # Fetch webpage content
        content = fetch_webpage_content(url)

        result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
        result_texts.append(result_text)

    # Format final response
    response = f"""🔍 Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""

    return response


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


# ============================================================================
# PageIndex Knowledge Retrieval Tools
# ============================================================================


@tool(parse_docstring=True)
def list_pageindex_documents() -> str:
    """Get the cached list of all documents in the PageIndex knowledge base.

    Call this AFTER decomposing the user question. Review the list (id, filename,
    description). Prioritize coverage: exclude ONLY the most obviously irrelevant
    docs. Keep case studies, industry reports, region docs when asking about cases.

    Returns:
        Formatted list of documents with: id, name (filename), description.
        Use the id values when calling query_pageindex(doc_ids=[...]).
    """
    try:
        return pageindex_cache.get_document_list()
    except Exception as e:
        return f"Error listing PageIndex documents: {e}"


@tool(parse_docstring=True)
def query_pageindex(
    query: str,
    doc_ids: Optional[List[str]] = None,
) -> str:
    """Query the PageIndex knowledge base using natural language.

    This tool searches through indexed company documents and returns relevant information
    with citations. Use this as your PRIMARY source for answering questions.

    CRITICAL RULES:
    - ALWAYS use this tool to find information before answering
    - NEVER make up information or use your own knowledge
    - ALWAYS cite sources from the response (document names and page numbers)
    - If information is not found, explicitly state "Information not found in knowledge base"

    When to use:
    - For ANY question about companies, services, or business information
    - When you need factual information with citations
    - When answering user queries (this should be your first action)

    Args:
        query: The question or information need in natural language.
               Be specific and detailed for better results.
        doc_ids: List of document IDs from recall step. Pass filtered IDs to narrow
                scope and reduce 504. Use list_pageindex_documents first.

    Returns:
        Relevant information from the knowledge base with citations including
        document names and page numbers. If no information is found, returns
        a message indicating the knowledge base doesn't contain the answer.

    Examples:
        query_pageindex(query="What are Ascentium's main service offerings?")
        query_pageindex(query="Tell me about the company's financial services")
        query_pageindex(
            query="What is the corporate structure?",
            doc_ids=["doc_123"]  # Search only in specific document
        )
    """
    try:
        return pageindex_cache.query(query=query, doc_ids=doc_ids)
    except Exception as e:
        return f"Error querying PageIndex: {e}"
