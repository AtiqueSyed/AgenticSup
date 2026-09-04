import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_intelligence_platform/backend"))

from openai import AsyncOpenAI
from app.core.config import settings

async def main():
    print(f"URL: {settings.OPENAI_BASE_URL}")
    print(f"KEY: {settings.OPENAI_API_KEY}")
    print(f"MODEL: {settings.DEFAULT_LLM_MODEL}")
    
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    try:
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": "Hello!"}],
            max_tokens=10
        )
        print("Success:", response.choices[0].message.content)
    except Exception as e:
        print("Error:", type(e).__name__)
        print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
