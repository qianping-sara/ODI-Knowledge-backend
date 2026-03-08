"""Quick test script to verify PageIndex integration."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test 1: Import the cache
print("Test 1: Importing PageIndex cache...")
try:
    from agent.research.pageindex_cache import pageindex_cache
    print("✅ PageIndex cache imported successfully")
except Exception as e:
    print(f"❌ Failed to import cache: {e}")
    exit(1)

# Test 2: Check API key
print("\nTest 2: Checking API key...")
api_key = os.getenv("PAGEINDEX_API_KEY")
if api_key:
    print(f"✅ API key found: {api_key[:10]}...")
else:
    print("❌ PAGEINDEX_API_KEY not found in environment")
    exit(1)

# Test 3: Check document list
print("\nTest 3: Loading document list...")
try:
    doc_list = pageindex_cache.get_document_list()
    print(f"✅ Document list loaded:")
    print(doc_list)
except Exception as e:
    print(f"❌ Failed to load documents: {e}")
    exit(1)

# Test 4: Import tools
print("\nTest 4: Importing tools...")
try:
    from agent.research.tools import query_pageindex, think_tool
    print("✅ Tools imported successfully")
    print(f"   - query_pageindex: {query_pageindex.name}")
    print(f"   - think_tool: {think_tool.name}")
except Exception as e:
    print(f"❌ Failed to import tools: {e}")
    exit(1)

# Test 5: Test a simple query
print("\nTest 5: Testing a simple query...")
try:
    result = pageindex_cache.query("越南设厂案例?（请确保你的答案包含知识来源详细说明，文件名/内容相关页码")
    print(f"✅ Query successful:")
    print(result[:500] + "..." if len(result) > 500 else result)
except Exception as e:
    print(f"❌ Query failed: {e}")
    exit(1)

# Test 6: Import agent
print("\nTest 6: Importing agent...")
try:
    from agent.entry import agent
    print("✅ Agent imported successfully")
    print(f"   - Agent type: {type(agent)}")
except Exception as e:
    print(f"❌ Failed to import agent: {e}")
    exit(1)

print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)
print("\nPageIndex integration is ready to use.")
print("You can now start the API server with: uv run uvicorn api.main:app --reload")

