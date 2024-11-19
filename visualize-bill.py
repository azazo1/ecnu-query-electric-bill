"""
可视化电量变化.
"""
import asyncio
import os
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib as mpl
import csv

from src import SERVER_PORT
from src.client import GuardClient, load_config
from websockets.asyncio.client import connect

DEGREE_CSV_FILE = "out/degree.csv"

# 解决中文显示的问题.
mpl.rcParams['font.family'] = 'SimHei'
plt.rcParams['axes.unicode_minus'] = False  # 步骤二 (解决坐标轴负数的负号显示问题)


async def download_data():
    os.makedirs(os.path.dirname(DEGREE_CSV_FILE), exist_ok=True)
    server_address = load_config()["server_address"]
    async with connect(f"ws://{server_address}:{SERVER_PORT}/") as client:
        gc = GuardClient(client)
        await gc.fetch_degree_file(DEGREE_CSV_FILE)


def load_data():
    timestamp = []
    degree = []
    try:
        with open(DEGREE_CSV_FILE, "r") as f:
            prev_degree_str = None
            for row in csv.reader(f):
                if prev_degree_str == row[1]:
                    continue
                prev_degree_str = row[1]
                timestamp.append(float(row[0]))
                degree.append(float(row[1]))
    except FileNotFoundError:
        pass
    return timestamp, degree


def main():
    asyncio.run(download_data())
    timestamp, degree = load_data()
    if not timestamp:
        print("no data")
        return
    start_date = datetime.fromtimestamp(timestamp[0])
    timestamp = list(
        map(lambda x: (x - start_date.timestamp()) / 3600 / 24, timestamp)
    )
    plt.plot(timestamp, degree, marker='o')
    plt.title(f'电量使用情况, 从 {start_date.strftime("%Y年%m月%d日%H时%M分%S秒")} 开始')
    plt.xlabel("时间(天)")
    plt.ylabel("电量(度)")
    plt.grid(True)
    plt.show()


if __name__ == '__main__':
    main()
