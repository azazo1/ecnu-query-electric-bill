import asyncio
import json
import logging
import os
import time
from json import JSONDecodeError
from typing import Optional

import httpx
import toml
import websockets
from websockets.asyncio.server import ServerConnection

from src import SERVER_PORT, Command, RetCode
from src.encryption import encrypt, decrypt

ROOM_FILE = "room.toml"
BILL_FILE = "bill.csv"

x_csrf_token = ""
cookies = {}
bill = -1

roomNo = ""
elcarea = -1
elcbuis = ""


def load_room():
    global roomNo, elcarea, elcbuis
    with open(ROOM_FILE, "r") as f:
        room = toml.load(f)
    roomNo = room["roomNo"]
    elcarea = room["elcarea"]
    elcbuis = room["elcbuis"]


async def query_electric_bill():
    """查询 electric bill 并把结果放在 bill 全局变量中, 返回是否成功获取."""
    global bill
    async with httpx.AsyncClient() as client:
        data = {
            "sysid": 1,
            "roomNo": roomNo,
            "elcarea": elcarea,
            "elcbuis": elcbuis
        }
        response = await client.post(
            "https://epay.ecnu.edu.cn/epaycas/electric/queryelectricbill",
            headers={
                "X-CSRF-TOKEN": x_csrf_token
            },
            data=data,
            cookies=cookies
        )
    try:
        ret = json.loads(response.text)
        if ret['retcode'] == 0 and ret['retmsg'] == "成功":
            bill = ret["restElecDegree"]
            return True
        else:
            return False
    except KeyError:
        return False
    except JSONDecodeError:
        return False


def get_electric_bill():
    return bill


async def send_ret(connection: ServerConnection, code: int, content: Optional[object] = None):
    ret = {"retcode": code}
    if content is not None:
        ret['content'] = content
    await connection.send(
        encrypt(json.dumps(ret))
    )


async def dorm_querying(connection: ServerConnection):
    global x_csrf_token, cookies
    async for message in connection:
        message = json.loads(decrypt(message))
        logging.info(f"Got message: {message}")
        if message["type"] == Command.GET_BILL:
            await send_ret(connection, RetCode.Ok, get_electric_bill())
        elif message["type"] == Command.POST_TOKEN:
            message = message["args"]
            if (isinstance(message, dict)
                    and isinstance(message.get('x_csrf_token'), str)
                    and isinstance(message.get('cookies'), dict)):
                x_csrf_token = message.get('x_csrf_token')
                cookies = message.get('cookies')
                await send_ret(connection, RetCode.Ok)
            else:
                await send_ret(connection, RetCode.ErrArgs)
        elif message["type"] == Command.FETCH_BILL_FILE:
            if not os.path.exists(BILL_FILE):
                await send_ret(connection, RetCode.ErrNoFile)
            else:
                with open(BILL_FILE, "r") as f:
                    await send_ret(connection, RetCode.Ok, f.read())


def record_bill():
    global bill
    logging.info(f"Recorded bill: {bill}.")
    with open(BILL_FILE, 'a') as f:
        f.write(f"{time.time():.2f}, {bill}\n")


async def bill_querying():
    global bill
    while True:
        try:
            query_result = await query_electric_bill()
            logging.info(f"{query_result=}.")
            if query_result:
                record_bill()
            else:
                bill = -1  # dorm 查询到 bill 为 -1 时就能直到需要重新设置 token 和 cookies.
        except Exception as e:
            logging.error(e)
        await asyncio.sleep(10)


async def server_main():
    load_room()
    server = await websockets.asyncio.server.serve(dorm_querying, "", SERVER_PORT)
    await asyncio.gather(server.serve_forever(), bill_querying())
