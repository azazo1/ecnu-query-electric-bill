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
DEGREE_FILE = "degree.csv"
FETCH_DEGREE_LINES = 1000

x_csrf_token = ""
cookies = {}
degree = -1

roomNo = ""
elcarea = -1
elcbuis = ""


def load_room():
    global roomNo, elcarea, elcbuis
    try:
        with open(ROOM_FILE, "r") as f:
            room = toml.load(f)
    except FileNotFoundError:
        room = {}
    roomNo = room.get("roomNo", "")
    elcarea = room.get("elcarea", -1)
    elcbuis = room.get("elcbuis", "")


def save_room(roomNo: str, elcarea: int, elcbuis: str):
    room_info = {"roomNo": roomNo, "elcarea": elcarea, "elcbuis": elcbuis}
    logging.info(f"room info saved: {room_info}")
    with open(ROOM_FILE, "w") as f:
        f.write(toml.dumps(room_info))
    load_room()


async def query_electric_degree():
    """
    查询 electric degree 并把结果放在 degree 全局变量中, 返回是否成功获取.

    - 成功查询时设置 degree 为剩余电量(度).
    - 如果宿舍信息没配置, degree 为 -2.
    - token 为设置或权限不足或宿舍信息不正确时, degree 为 -1.
    """
    global degree
    if not roomNo or elcarea < 0 or not elcbuis:
        # 没有配置宿舍信息.
        degree = -2
        return False
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
            degree = ret["restElecDegree"]
            return True
        else:
            degree = -1
            return False
    except KeyError:
        degree = -1
        return False
    except JSONDecodeError:
        degree = -1
        return False


async def send_ret(connection: ServerConnection, code: int, content: Optional[object] = None):
    ret = {"retcode": code}
    if content is not None:
        ret['content'] = content
    await connection.send(
        encrypt(json.dumps(ret))
    )


def remove_duplicate_degrees_in_file():
    prev_degree = -1
    new = []
    with open(DEGREE_FILE, "r") as f:
        for line in f:
            timestamp, degree_ = line.split(',')
            degree_ = float(degree_)
            if degree_ == prev_degree:
                continue
            new.append(','.join((timestamp, str(degree_))))
            prev_degree = degree_
    with open(DEGREE_FILE, "w") as f:
        f.write('\n'.join(new))


async def dorm_querying(connection: ServerConnection):
    global x_csrf_token, cookies
    async for message in connection:
        message = json.loads(decrypt(message))
        logging.info(f"Got message: {message['type']}")
        logging.debug(f"Whole message: {message}")
        if message["type"] == Command.GET_DEGREE:
            await send_ret(connection, RetCode.Ok, degree)
        elif message["type"] == Command.POST_TOKEN:
            args = message.get("args")
            if (isinstance(args, dict)
                    and isinstance(args.get('x_csrf_token'), str)
                    and isinstance(args.get('cookies'), dict)):
                x_csrf_token = args.get('x_csrf_token')
                cookies = args.get('cookies')
                await send_ret(connection, RetCode.Ok)
            else:
                await send_ret(connection, RetCode.ErrArgs)
        elif message["type"] == Command.FETCH_DEGREE_FILE:
            if not os.path.exists(DEGREE_FILE):
                await send_ret(connection, RetCode.ErrNoFile)
            else:
                remove_duplicate_degrees_in_file()
                with open(DEGREE_FILE, "r") as f:
                    await send_ret(connection, RetCode.Ok,
                                   "\n".join(f.read().splitlines()[-FETCH_DEGREE_LINES:]))
        elif message["type"] == Command.POST_ROOM:
            args = message.get("args")
            if (isinstance(args, dict)
                    and isinstance(args.get('roomNo'), str)
                    and isinstance(args.get('elcarea'), int)
                    and isinstance(args.get('elcbuis'), str)):
                save_room(
                    roomNo=args.get('roomNo'),
                    elcarea=args.get('elcarea'),
                    elcbuis=args.get('elcbuis')
                )
                await send_ret(connection, RetCode.Ok)
            else:
                await send_ret(connection, RetCode.ErrArgs)


def record_degree():
    global degree
    logging.info(f"Recorded degree: {degree}.")
    with open(DEGREE_FILE, 'a') as f:
        f.write(f"{time.time():.2f}, {degree}\n")


async def degree_querying():
    global degree
    while True:
        try:
            query_result = await query_electric_degree()
            logging.info(f"{query_result=}, {degree=}.")
            if query_result:
                record_degree()
        except Exception as e:
            logging.error(e)
        await asyncio.sleep(10)


async def server_main():
    load_room()
    server = await websockets.asyncio.server.serve(dorm_querying, "", SERVER_PORT)
    await asyncio.gather(server.serve_forever(), degree_querying())
