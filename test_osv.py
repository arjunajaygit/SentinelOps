import asyncio
import aiohttp

async def test():
    payload = {
        "queries": [
            {"version": "1.25.10", "package": {"name": "urllib3", "ecosystem": "PyPI"}}
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.osv.dev/v1/querybatch", json=payload) as response:
            print(await response.json())

asyncio.run(test())
