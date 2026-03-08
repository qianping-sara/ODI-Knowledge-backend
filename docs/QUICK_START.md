# 🚀 Quick Start Guide - PageIndex Integration

## ✅ Setup Complete!

Your PageIndex integration is ready to use. Here's how to get started.

## 📋 What's Been Done

1. ✅ **PageIndex SDK** installed and configured
2. ✅ **Database** set up (SQLite for local development)
3. ✅ **Agent** configured to use PageIndex only
4. ✅ **Tools** created for knowledge retrieval
5. ✅ **Prompts** updated for citation-based responses
6. ✅ **26 documents** loaded into PageIndex cache

## 🎯 How to Use

### Step 1: Start the API Server

```bash
uv run uvicorn api.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Step 2: Test with the Test Script

In a **new terminal window**:

```bash
python test_api_chat.py
```

This will:
- Create a new chat session
- Ask several questions about Ascentium and Vietnam
- Display the agent's responses with citations
- Show the conversation history

### Step 3: Try Your Own Questions

You can also test manually using curl:

```bash
# Create a session
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "My Test Session"}' \
  | jq .

# Send a message (save the session_id from above)
curl -X POST http://localhost:8000/api/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "message": "What services does Ascentium offer?",
    "stream": false
  }' \
  | jq .
```

## 🤖 How the Agent Works

### 1. Question Decomposition
When you ask a question, the agent:
- Breaks it down into multiple specific topics
- Example: "Tell me about Ascentium" →
  - Topic 1: Corporate services
  - Topic 2: Financial services
  - Topic 3: HR services
  - Topic 4: Other specialized services

### 2. Parallel Knowledge Retrieval
- Calls `query_pageindex` tool for each topic **simultaneously**
- Faster than sequential queries
- Each query searches across all 26 documents

### 3. Reflection
- Uses `think_tool` to assess results
- Checks if the question is fully answered
- Decides if more queries are needed

### 4. Synthesis with Citations
- Combines all retrieved information
- **Every fact includes source citation**: `[Source: Document Name, Page X]`
- Explicitly states if information is not found

## 📚 Available Knowledge

The system has access to documents about:

**Ascentium Services:**
- Business Intelligence solutions
- Market entry strategies
- Location advisory and site selection
- Partner identification services

**Vietnam Business:**
- Tax and audit compliance timelines
- Regulatory updates (2025-2026)
- Profit repatriation procedures
- Company setup questionnaires
- ERP services

**Case Studies:**
- Manufacturing relocation (power tools, hydraulics)
- Electronics company cost reduction
- Swiss market entry to Indonesia
- Multi-country benchmarking

## 💡 Example Questions to Try

### Simple Questions:
- "What services does Ascentium offer?"
- "What are the Vietnam tax compliance deadlines for 2025?"
- "How do I repatriate profits from Vietnam?"

### Complex Questions:
- "Tell me about Ascentium's business intelligence services and provide case study examples"
- "What are the key regulatory changes in Vietnam for 2025 and how do they impact foreign investors?"
- "Compare the location selection process with partner identification services"

### Follow-up Questions:
- "Can you provide more details about the case studies?"
- "What documents do I need for profit repatriation?"
- "Tell me more about the ERP services"

## 🔍 Observing the Agent's Work

### Check the Server Logs

In the terminal where you ran `uvicorn`, you'll see:
- Tool calls: `query_pageindex(query="...")`
- Reflections: `think_tool(reflection="...")`
- Agent reasoning steps

### Example Log Output:
```
INFO: Tool call: query_pageindex
INFO: Query: "What corporate services does Ascentium offer?"
INFO: Tool call: query_pageindex
INFO: Query: "What financial services does Ascentium provide?"
INFO: Tool call: think_tool
INFO: Reflection: "I have comprehensive information about services..."
```

## ⚙️ Configuration

### Current Setup (Local Development)

**Database:** SQLite (`company_research.db`)
**Knowledge Source:** PageIndex only (Tavily disabled)
**Agent Mode:** Single agent with parallel tool calls
**Documents:** 26 documents loaded at startup

### Environment Variables (`.env`)

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./company_research.db

# PageIndex
PAGEINDEX_API_KEY=7f4f5f4a7a...

# Azure OpenAI (for the agent)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_DEPLOYMENT=gpt-5.2-chat
```

## 🐛 Troubleshooting

### Server won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill the process if needed
kill -9 <PID>
```

### Database errors
```bash
# Re-run migrations
uv run alembic upgrade head
```

### PageIndex not working
```bash
# Test PageIndex integration
uv run python test_pageindex_integration.py
```

### Agent not citing sources
- Check server logs for tool calls
- Verify PageIndex API key is set
- Ensure documents are loaded (check startup logs)

## 📁 Key Files

- `agent/entry.py` - Agent configuration
- `agent/research/tools.py` - PageIndex tools
- `agent/research/prompts_cust.py` - System prompts
- `agent/research/pageindex_cache.py` - Document cache
- `test_api_chat.py` - API test script
- `test_pageindex_integration.py` - Integration test

## 🎉 Next Steps

1. **Test the system** with various questions
2. **Monitor citations** - ensure all facts have sources
3. **Check reflection quality** - is the agent decomposing questions well?
4. **Evaluate responses** - are they comprehensive and accurate?

## 📞 Need Help?

- Check `PAGEINDEX_INTEGRATION.md` for technical details
- Check `DATABASE_SETUP.md` for database configuration
- Review server logs for debugging information

---

**Ready to test?** Run:
```bash
# Terminal 1
uv run uvicorn api.main:app --reload

# Terminal 2
python test_api_chat.py
```

