# ECNU 宿舍电费自动查询
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Server](https://img.shields.io/badge/Server-Linux%20%7C%20Windows%20%7C%20macOS-success)](.)
[![Client](https://img.shields.io/badge/Client-Windows-important)](.)
[![Status](https://img.shields.io/badge/Status-Active-success)](.)
[![ECNU](https://img.shields.io/badge/For-ECNU-FF6B35)](https://www.ecnu.edu.cn/)

经常烦恼忘记充电费导致宿舍断电?
此脚本可以为广大 ECNUer 实现电量不足时自动提醒, 防止意外断电的尴尬情况.

## 功能介绍

本脚本会对宿舍的电费情况进行持续监控, 并在宿舍电费不足的时候给予提醒.

## 部署方法

### 要求

- 一台云服务器, aliyun 服务器有 99/年 套餐, 基本可以人手一台.
  - 云服务器需要有公网 ip.
  - 云服务器需要配置 ssh 以进行操作.
  - 云服务器需要可以联网.
- 手上一台电脑.
  - 需要有 edge 浏览器, selenium 框架中使用 edge.
  - 可以联网.
  - 安装 python (>=3.10).

### 服务端部署

服务端用于持续对电费账单的查询和记录, 并输出电费随时间变化的表格, 并将数据提供给客户端.

以下步骤皆在服务器中进行.

#### 安全组/防火墙设置

此为云服务器设置, 在云服务器上部署的服务端要让外界访问需要放行特定端口.

请为 30530 端口放行 TCP 连接.

如果是 CentOS 等操作系统, 需要使用命令行配置防火墙:

```shell
sudo firewall-cmd --zone=public --add-port=30530/tcp --permanent
sudo firewall-cmd --reload
```

#### 信息填写

首先将项目代码解压到自己的服务器.

在项目根目录创建文件 key.toml, 填写以下内容:

```toml
# aes256cbc 加密传输密钥.
key = "..." # 32 个字符的字符串做密钥.
iv = "..." # 16 个字符的初始化向量字符串.
# 最好选用 ascii 字符.
```

- `...`: 请自行填写, 注意不是 ecnu 帐号密码, 下文客户端中要使用相同的内容.

(此步可选做, 详见 [宿舍信息上传](#宿舍信息上传))同目录下创建 room.toml, 填写宿舍信息:

```toml
# 以下信息需要抓包获取, 见 https://epay.ecnu.edu.cn/epaycas/, 点击水电缴费中的电费, 暂时不展开说明.
# 以下信息后面的值仅供参考, 需要自己修改才能生效, 否则查询到的是别处宿舍的电费.
roomNo = "21102_MH_95_326"
elcarea = 102
elcbuis = "new-95_MH"
```

#### 环境准备

进入项目目录, 运行:

```shell
uv tool install -e .
```

#### 运行

在项目根目录中运行 (测试时使用 python3.10, 3.12, 可正常运行):

```shell
billqueryserver
```

运行之后显示 `degree=-1` 或 `degree=-2` 为第一次启动正常现象, 客户端上传相应数据后即可正常查询.

如果需要脱离 ssh 运行, 可以使用 `screen` 命令, 提供一个简单的参考.

```shell
~/ecnu-query-electric-bill# screen -S query-bill # -S 后面的是 screen 创建的后台任务名字, 可自己修改.
# 此处进入 screen.
~/ecnu-query-electric-bill# billqueryserver # 在 screen 中运行.
# 使用键盘快捷键: ctrl a 然后按 d.
# 此处退出 screen.
~/ecnu-query-electric-bill# exit # 可以退出 ssh 而 screen 中的任务不会终止.

# 此处再次进入 ssh.
~/ecnu-query-electric-bill# screen -r query-bill # 重新进入 screen 后台任务, 进入后可以看到标准输出.
```

### 客户端部署

客户端部署在个人电脑上, 随个人电脑启动时开始运行, 电脑关机时结束运行即可.

客户端主要用于 token 的获取, 由于 token 获取需要使用 ecnu 统一登录, 无法避免人手操作, 故只能安排在客户端.

>[!INFO]
> 注: ecnu 的登录认证如果长时间没有活动则会自动过期, 故需要部署服务端以保持 token 活性, 减少用户手动登录的次数.

#### 信息填写

将项目代码解压到个人电脑.

在项目根目录创建文件 key.toml, 填写以下内容:

```toml
# 以下内容和服务端需保持已知, 否则无法成功进行加密通信.
key = "..."
iv = "..."
```

在项目根目录创建文件 client.toml, 填写以下内容.

```toml
server_address = "..." # 云服务器的公网 ip 地址.
alert_degree = 10 # 低于 10 度电时显示警告, 此项可以不填, 默认为 10.
```

#### 环境准备

安装:

```shell
uv tool install -e .
```

运行

```
billqueryclient
```

> 如果需要后台运行, 使用 `gbillqueryclient`.

然后在 [Edge WebDriver](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/?form=MA13LH#downloads)
下载 edge 最新的浏览器驱动压缩包, 并确保 edge 和其版本匹配, 然后解压其中的 msedgedriver.exe 到
python 安装目录.

#### 运行

建议让脚本开机自启动, 及时检查服务端上 token 的活性.

- 如果是 windows 电脑, 可以使用 `Win + R`, 然后输入 `shell:startup`,
  在其中创建快捷方式 `billqueryclient`, 起始目录为项目目录.
- 如果是其他操作系统, 请自行参考其他方法.

运行

```
billqueryclient
```

##### 登录失效提醒

运行时, 如果服务端 token 失效, 客户端会检测到并弹窗提示用户重新登录自己的 ecnu 帐号,
token 使用 aes256cbc 加密传输.

##### 宿舍信息上传

如果前面配置服务端时, 没有填写 room.toml 文件, 那么服务端启动时没有宿舍的信息, 无法查询到宿舍电量.

客户端启动后检测到这一情况会提醒用户填写宿舍信息后自动上传, 此操作通常只出现一次, 服务器会自动保存宿舍信息.

如果想手动再次更改宿舍信息, 请在个人电脑上运行 config-room.py 文件, 此操作会覆盖原来服务端保存的宿舍信息.

## 脚本失效提醒

由于网站可能随时间变化其 api, 故脚本随时可能失效.

2025 年 4 月 10 日测试有效.
