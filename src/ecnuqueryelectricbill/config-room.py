"""
配置服务端的宿舍信息, 请在个人电脑上运行.
"""

import asyncio
from websockets.asyncio.client import connect

from ecnuqueryelectricbill import SERVER_PORT
from ecnuqueryelectricbill.client import GuardClient, load_config, alert


async def main():
    # 已经在项目根目录见 __init__.py

    config = load_config()
    server_address = config["server_address"]
    async with connect(f"ws://{server_address}:{SERVER_PORT}/") as client:
        gc = GuardClient(client)
        room = GuardClient.ask_for_room()
        if room is not None:
            await gc.post_room(**room)
            alert("成功上传", "成功上传宿舍信息")


if __name__ == "__main__":
    asyncio.run(main())
