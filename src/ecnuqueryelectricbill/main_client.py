import asyncio
from PySide6.QtWidgets import QApplication
from ecnuqueryelectricbill.client import client_main
import qasync


def setup_asyncio():
    """配置AsyncIO事件循环并在应用退出时正确关闭"""
    loop = qasync.QEventLoop(QApplication.instance())
    asyncio.set_event_loop(loop)
    QApplication.instance().aboutToQuit.connect(lambda: loop.stop())


def main():
    # 已经在项目根目录见 __init__.py
    app = QApplication([])
    setup_asyncio()

    # 在Qt事件循环中运行异步任务
    asyncio.run(client_main())

    # 启动Qt事件循环
    app.exec()


if __name__ == "__main__":
    main()
