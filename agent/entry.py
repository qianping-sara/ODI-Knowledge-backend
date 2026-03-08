"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.
"""

import os
from datetime import datetime

# from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_openai import AzureChatOpenAI

from agent.research.prompts_cust import PAGEINDEX_RESEARCH_INSTRUCTIONS
from agent.research.tools import list_pageindex_documents, query_pageindex, think_tool

# Disabled tools (preserved for future use)
# from agent.research.tools import tavily_search
# from agent.research.prompts_cust import (
#     RESEARCH_WORKFLOW_INSTRUCTIONS,
#     RESEARCHER_INSTRUCTIONS,
#     SUBAGENT_DELEGATION_INSTRUCTIONS,
# )

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# PageIndex-only instructions
INSTRUCTIONS = PAGEINDEX_RESEARCH_INSTRUCTIONS.format(date=current_date)

# Disabled: Sub-agent approach (preserved for future use)
# max_concurrent_research_units = 3
# max_researcher_iterations = 3
# research_sub_agent = {
#     "name": "research-agent",
#     "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
#     "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
#     "tools": [tavily_search, think_tool],
# }

# Model Gemini 3
# model = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.0)

# Model Claude 4.5
# model = init_chat_model(model="anthropic:claude-sonnet-4-5-20250929", temperature=0.0)


model = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    # temperature=0.0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Create the agent with PageIndex tools only
agent = create_deep_agent(
    model=model,
    tools=[list_pageindex_documents, query_pageindex, think_tool],
    system_prompt=INSTRUCTIONS,
    subagents=[],  # No sub-agents for initial simple approach
    backend=FilesystemBackend(root_dir=".", virtual_mode=True)
)
