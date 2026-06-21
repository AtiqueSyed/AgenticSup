import asyncio
from openai import AsyncOpenAI

async def test():
    client = AsyncOpenAI(
        api_key="bx_f8b75a2444b04444a058f65dab8de125",
        base_url="https://2ba4deroudq53d3h3lusq4gflq0quvyn.lambda-url.ap-south-1.on.aws/v1"
    )
    try:
        response = await client.chat.completions.create(
            model="qwen.qwen3-coder-30b-a3b-instruct",
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(response)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
