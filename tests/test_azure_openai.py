"""Test Azure OpenAI configuration."""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage

# Load environment variables
load_dotenv()

print("🔍 Testing Azure OpenAI Configuration")
print("=" * 60)

# Print configuration
print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
print(f"Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT')}")
print(f"API Version: {os.getenv('AZURE_OPENAI_API_VERSION')}")
print(f"API Key: {'*' * 20 if os.getenv('AZURE_OPENAI_API_KEY') else 'NOT SET'}")
print("=" * 60)

try:
    # Create model
    model = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        max_tokens=100,
        timeout=30,
        max_retries=2,
    )
    
    print("\n✅ Model created successfully")
    
    # Test simple invocation
    print("\n📤 Sending test message: 'Hello, how are you?'")
    response = model.invoke([HumanMessage(content="Hello, how are you?")])
    
    print(f"\n✅ Response received:")
    print(f"🤖 {response.content}")
    print("\n" + "=" * 60)
    print("✅ Azure OpenAI configuration is working!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

