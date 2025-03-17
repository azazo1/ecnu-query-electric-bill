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

from ecnuqueryelectricbill import Command, SERVER_PORT
from ecnuqueryelectricbill.encryption import decrypt, encrypt
from selenium.webdriver import Edge

CLIENT_CONFIG = "client.toml"
alert_degree = 10  # 警告电量 (度), 当宿舍电量低于当前电量时客户端显示警告.


def load_config():
    global alert_degree
    with open(CLIENT_CONFIG, "r") as f:
        ret = toml.load(f)
        alert_degree = ret.get("alert_degree", alert_degree)
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


def alert(title: str, text: str, button: str = "好的", topmost=True) -> bool:
    """显示对话弹窗, 如果用户表示同意操作, 返回 True, 如果用户关闭弹窗返回 False."""
    grant = False

    def grant_it():
        nonlocal grant
        grant = True
        root.destroy()

    root = tk.Tk()
    root.title(title)
    root.wm_attributes("-topmost", topmost)
    tk.Label(root, text=text).pack()
    tk.Button(root, text=button, command=grant_it).pack()
    root.mainloop()
    return grant


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

    async def fetch_degree(self):
        await self._send_command(Command.GET_DEGREE)
        ret = await self._recv_ret()
        if ret["retcode"] != 0:
            raise ValueError(f"retcode is not zero: {ret}.")
        return ret["content"]

    async def fetch_degree_routine(self):
        """对此 Task 调用 cancel 方法来停止运行."""
        prev_degree = -1
        while not asyncio.current_task().cancelled():
            degree: float = await self.fetch_degree()
            if degree == -1:
                logging.info("login invalid.")
                # 从这里开始登录失效了, 重新登录, 需要启动浏览器.
                token = self.ask_for_login()
                if token is not None:
                    await self.post_token(**token)
                    alert("成功上传", "成功上传登录 token.")
                    logging.info("token posted.")
            elif degree == -2:
                logging.info("room info missing.")
                room = self.ask_for_room()
                if room is not None:
                    await self.post_room(**room)
                    alert("成功上传", "成功上传宿舍信息.")
                    logging.info("room posted.")
            else:
                logging.info(f"{degree=}.")
                if degree < alert_degree:
                    alert(
                        title="电费不足",
                        text="请及时进行电量的充值, 以防止意外断电的情况."
                    )
                elif degree > prev_degree > 0:  # prev_degree < 0 为特殊情况.
                    alert(
                        title="电量充值",
                        text=f"检测到电量增加: 增加度数为 {degree - prev_degree:.2f}."
                    )
                prev_degree = degree
            await asyncio.sleep(10)

    def __await__(self):
        task = asyncio.create_task(self.fetch_degree_routine())
        yield from task
        return task.result()

    @classmethod
    def ask_for_login(cls):
        if not alert(title="请登录",
                     text="登录信息已失效,\n"
                          "请在打开的界面重新登录,\n"
                          "然后等待浏览器自动关闭."):
            return None
        driver = Edge()
        try:
            driver.get(
                "https://epay.ecnu.edu.cn/epaycas/electric/load4electricbill?elcsysid=1"
            )  # 这个网址会重定向至登录界面.
            WebDriverWait(driver, timeout=60 * 60).until(
                EC.url_matches(r'https://epay.ecnu.edu.cn')  # 等待登录之后的重定向.
            )
            j_session_id = driver.get_cookie("JSESSIONID")['value']
            cookie = driver.get_cookie("cookie")['value']
            # 在 main frame 中以获取 x_csrf_token.
            meta = driver.find_element(By.XPATH, "/html/head/meta[4]")
            x_csrf_token = meta.get_property("content")
            rst = {
                "x_csrf_token": x_csrf_token,
                "cookies": {
                    "JSESSIONID": j_session_id,
                    "cookie": cookie
                }
            }
            logging.debug("Got login info: {}".format(rst))
            return rst
        finally:
            driver.quit()

    @classmethod
    def ask_for_room(cls):
        if not alert(title="宿舍信息未配置",
                     text="请点击确认按钮, 先登录 ECNU 帐号,\n"
                          "然后对自己宿舍的电量进行一次查询,\n"
                          "浏览器会读取宿舍信息并自动关闭."):
            return None
        driver = Edge()
        try:
            driver.get(
                "https://epay.ecnu.edu.cn/epaycas/electric/load4electricbill?elcsysid=1"
            )  # 这个网址会重定向至登录界面.
            # 先等待用户登录.
            WebDriverWait(driver, timeout=60 * 60).until(
                EC.url_matches(r'https://epay.ecnu.edu.cn')
            )
            # 等待按钮出现, 放置回调函数.
            WebDriverWait(driver, timeout=60 * 60).until(
                EC.presence_of_element_located((By.ID, "queryBill"))
            )
            driver.execute_script("""
            let button = document.querySelector("#queryBill");
            button.onclick = function() {
                let a = document.createElement("a");
                a.id = "query_clicked"; // 查询按钮按下时添加新元素, 终结下面的 WebDriverWait.
                document.body.appendChild(a);
            }
            """)
            WebDriverWait(driver, timeout=60 * 60).until(
                EC.presence_of_element_located((By.ID, "query_clicked"))
            )
            elcbuis = driver.find_element(By.ID, "elcbuis").get_property("value")
            elcarea = driver.find_element(By.ID, "elcarea").get_property("value")
            elcroom = driver.find_element(By.ID, "elcroom").get_property("value")
            return {
                "elcbuis": elcbuis,
                "elcarea": int(elcarea),
                "roomNo": elcroom,
            }
        finally:
            driver.quit()

    async def post_room(self, roomNo: str, elcarea: int, elcbuis: str):
        await self._send_command(
            Command.POST_ROOM,
            {"roomNo": roomNo, "elcarea": elcarea, "elcbuis": elcbuis}
        )
        ret = await self._recv_ret()
        if ret["retcode"] != 0:
            raise ValueError(f"retcode is not zero: {ret}.")

    async def fetch_degree_file(self, save_file: str):
        await self._send_command(Command.FETCH_DEGREE_FILE)
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
