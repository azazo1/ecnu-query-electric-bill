from ecnuqueryelectricbill.server import server_main
import asyncio


def main():
    # 已经在项目根目录见 __init__.py
    asyncio.run(server_main())


if __name__ == "__main__":
    main()
