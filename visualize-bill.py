"""
可视化电量变化.
"""
import asyncio
from datetime import datetime
import matplotlib.pyplot as plt
import csv

from src import SERVER_PORT
from src.client import GuardClient, load_config
from websockets.asyncio.client import connect

BILL_CSV_FILE = "out/bill.csv"


async def download_data():
    server_address = load_config()["server_address"]
    async with connect(f"ws://{server_address}:{SERVER_PORT}/") as client:
        gc = GuardClient(client)
        await gc.fetch_bill_file(BILL_CSV_FILE)


def load_data():
    timestamp = []
    bill = []
    try:
        with open(BILL_CSV_FILE, "r") as f:
            prev_bill_str = None
            for row in csv.reader(f):
                if prev_bill_str == row[1]:
                    continue
                prev_bill_str = row[1]
                timestamp.append(float(row[0]))
                bill.append(float(row[1]))
    except FileNotFoundError:
        pass
    return timestamp, bill


def main():
    asyncio.run(download_data())
    timestamp, bill = load_data()
    if not timestamp:
        print("no data")
        return
    start_date = datetime.fromtimestamp(timestamp[0])
    timestamp = list(
        map(lambda x: (x - start_date.timestamp()) / 3600, timestamp)
    )
    plt.plot(timestamp, bill, marker='o')
    plt.title(f'电量使用情况, 从 {start_date.strftime("%Y年%m月%d日%H时%M分%S秒")} 开始')
    plt.xlabel("时间(小时)")
    plt.ylabel("电量(度)")
    plt.grid(True)
    plt.show()


if __name__ == '__main__':
    main()
