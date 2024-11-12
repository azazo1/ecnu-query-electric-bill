import asyncio
import tkinter as tk
import json
import logging
import traceback
from typing import Optional

import toml
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from websockets.asyncio.client import connect, ClientConnection

from src import Command, SERVER_PORT
from src.encryption import decrypt, encrypt
from selenium.webdriver import Edge

CLIENT_CONFIG = "client.toml"
alert_bill = 10  # 警告电量 (度), 当宿舍电量低于当前电量时客户端显示警告.


def load_config():
    global alert_bill
    with open(CLIENT_CONFIG, "r") as f:
        ret = toml.load(f)
        alert_bill = ret.get("alert_bill", alert_bill)
        return ret


async def _post_token_example():
    server_address = load_config()["server_address"]
    client = await connect(f"ws://{server_address}:{SERVER_PORT}/")
    await client.send(encrypt(json.dumps(
        {"type": Command.POST_TOKEN, "args": {
            "x_csrf_token": "...",
            "cookies": {
                "JSESSIONID": "...",
                "cookie": "..."
            }
        }}
    )))
    print(decrypt(await client.recv()))
    await client.close()


class GuardClient:
    """
    保证 server 始终取得正确的 token 和 cookies.
    需要手动关闭 client.
    """

    def __init__(self, client: ClientConnection):
        self.client = client

    async def _send_command(self, type_: str, args: Optional[object] = None):
        dic = {"type": type_}
        if args is not None:
            dic["args"] = args
        await self.client.send(encrypt(
            json.dumps(dic)
        ))

    async def _recv_ret(self):
        return json.loads(decrypt(await self.client.recv()))

    async def post_token(self, x_csrf_token: str, cookies: dict[str, str]):
        await self._send_command(
            Command.POST_TOKEN,
            {"x_csrf_token": x_csrf_token, "cookies": cookies}
        )
        ret = await self._recv_ret()
        if ret["retcode"] != 0:
            raise ValueError(f"retcode is not zero: {ret}.")

    async def fetch_bill(self):
        await self._send_command(Command.GET_BILL)
        ret = await self._recv_ret()
        if ret["retcode"] != 0:
            raise ValueError(f"retcode is not zero: {ret}.")
        return ret["content"]

    async def fetch_bill_routine(self):
        """对此 Task 调用 cancel 方法来停止运行."""
        prev_login = True
        prev_bill = -1
        while not asyncio.current_task().cancelled():
            bill: float = await self.fetch_bill()
            if bill == -1:
                if prev_login:
                    logging.info(f"login invalid.")
                    # 从这里开始登录失效了, 重新登录, 需要启动浏览器.
                    await self.post_token(**self.ask_for_login())
                prev_login = False
            else:
                logging.info(f"{bill=}.")
                if bill < alert_bill:
                    root = tk.Tk()
                    root.title("电费不足!")
                    root.wm_attributes("-topmost", True)
                    tk.Label(root, text="请及时进行电费的充值, 以防止意外断电的情况.").pack()
                    tk.Button(root, text="好的", command=root.destroy).pack()
                    root.mainloop()
                elif bill > prev_bill and prev_login:
                    root = tk.Tk()
                    root.title("电量充值")
                    root.wm_attributes("-topmost", True)
                    tk.Label(root,
                             text=f"检测到电量增加: 增加度数为 {bill - prev_bill:.2f}.").pack()
                    tk.Button(root, text="好的", command=root.destroy).pack()
                    root.mainloop()
                prev_bill = bill
                prev_login = True
            await asyncio.sleep(10)

    def __await__(self):
        task = asyncio.create_task(self.fetch_bill_routine())
        yield from task
        return task.result()

    @classmethod
    def ask_for_login(cls):
        root = tk.Tk()
        root.title("请登录")
        tk.Label(root,
                 text="登录信息已失效, 请在打开的界面重新登录, 然后等待浏览器自动关闭.").pack()
        tk.Button(root, text="打开浏览器界面", command=root.destroy).pack()
        root.mainloop()
        driver = Edge()
        try:
            driver.get("https://epay.ecnu.edu.cn/epaycas/")  # 这个网址会重定向至登录界面.
            WebDriverWait(driver, timeout=60 * 60).until(
                EC.url_matches(r'https://epay.ecnu.edu.cn')  # 等待登录之后的重定向.
            )
            j_session_id = driver.get_cookie("JSESSIONID")['value']
            cookie = driver.get_cookie("cookie")['value']
            # 进入 main frame 以获取 x_csrf_token.
            driver.get("https://epay.ecnu.edu.cn/epaycas/electric/load4electricbill?elcsysid=1")
            meta = driver.find_element(By.XPATH, "/html/head/meta[4]")
            x_csrf_token = meta.get_property("content")
            rst = {
                "x_csrf_token": x_csrf_token,
                "cookies": {
                    "JSESSIONID": j_session_id,
                    "cookie": cookie
                }
            }
            logging.info("Got login info: {}".format(rst))
            return rst
        finally:
            driver.quit()

    async def fetch_bill_file(self, save_file: str):
        await self._send_command(Command.FETCH_BILL_FILE)
        ret = await self._recv_ret()
        if ret["retcode"] != 0:
            raise ValueError(f"retcode is not zero: {ret}.")
        with open(save_file, "w") as f:
            f.write(ret["content"])


async def client_main():
    config = load_config()
    server_address = config["server_address"]
    while True:
        try:
            async with connect(f"ws://{server_address}:{SERVER_PORT}/") as client:
                await GuardClient(client)
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(3)

# todo 服务端 bill 为 -2 的时候表示没有配置好宿舍信息, 客户端使用爬虫提示用户登录并选择自己的宿舍然后提取用户信息.
