"""
可视化电量变化.
"""

import asyncio
import math
import os
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib as mpl
import csv

from ecnuqueryelectricbill import SERVER_PORT
from ecnuqueryelectricbill.client import GuardClient, load_config
from websockets.asyncio.client import connect

DEGREE_CSV_FILE = "out/degree.csv"

# 解决中文显示的问题.
mpl.rcParams["font.family"] = "SimHei"
plt.rcParams["axes.unicode_minus"] = False  # 步骤二 (解决坐标轴负数的负号显示问题)


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


def smooth(timestamp, data, alpha=0.9, k=0.6):
    """
    数据平滑, 但是要解决非相同时间间隔的数据影响.

    # 符号解释

    - alpha 为保留系数, 越大数据变动越慢.
    - a 为保留系数实例, 经过 alpha 与间隔时间比例相乘得到, 远的数据保留系数实例 a 越小, 近的数据(高频)保留系数实例 a 越大.
    - k 为距离促动速度, 越大则同距离时数据对变动速度影响越大.

    alpha = 0, k = 0 时, 函数输出的数据和原始数据相同.
    """
    assert len(data) == len(timestamp)
    if not data:
        return []
    max_delta_time = 0
    for i in range(len(timestamp) - 1):
        max_delta_time = max(max_delta_time, timestamp[i + 1] - timestamp[i])
    r = data[0]
    rst = []
    for i in range(len(data)):
        if i == 0:
            delta_time = 0
        else:
            delta_time = timestamp[i] - timestamp[i - 1]
        a = alpha * math.exp(-k * (delta_time / max_delta_time))
        r = r * a + data[i] * (1 - a)
        rst.append(r)
    return rst


def consuming_speed(timestamp, degree):
    t, s = [], []  # 消耗速度时间戳和消耗速度, 单位: 度/天.
    for i in range(len(timestamp) - 1):
        delta_time = timestamp[i + 1] - timestamp[i]
        t.append(delta_time / 2 + timestamp[i])
        s.append(max(degree[i] - degree[i + 1], 0) / delta_time * 3600 * 24)
    s = smooth(t, s)
    return t, s


def main():
    # 已经在项目根目录见 __init__.py
    asyncio.run(download_data())
    timestamp, degree = load_data()
    if not timestamp:
        print("no data")
        return
    start_date = datetime.fromtimestamp(timestamp[0])
    day_stamp = list(map(lambda x: (x - start_date.timestamp()) / 3600 / 24, timestamp))
    fig, ax = plt.subplots()
    ax.plot(day_stamp, degree, marker="o", label="电量")
    ax.set_title(
        f"电量使用情况, 从 {start_date.strftime('%Y年%m月%d日%H时%M分%S秒')} 开始"
    )
    ax.set_xlabel("时间(天)")
    ax.set_ylabel("电量(度)")
    ax.grid(True)

    timestamp, speed = consuming_speed(timestamp, degree)
    day_stamp = [(i - start_date.timestamp()) / 3600 / 24 for i in timestamp]
    ax1 = ax.twinx()
    ax1.plot(day_stamp, speed, "r--", label="电量消耗速度")
    ax1.set_ylim(0, 20)
    ax1.set_ylabel("电量消耗速度(度/天)")

    ax.legend(loc="upper left")
    ax1.legend(loc="upper right")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
