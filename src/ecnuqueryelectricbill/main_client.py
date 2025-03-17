import asyncio
from ecnuqueryelectricbill.client import client_main


def main():
    # 已经在项目根目录见 __init__.py
    asyncio.run(client_main())


if __name__ == "__main__":
    main()
