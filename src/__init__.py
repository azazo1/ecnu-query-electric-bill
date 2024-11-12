import logging

import toml
import os
from pathlib import Path

SERVER_PORT = 50530
KEY_FILE = 'key.toml'

os.chdir(Path(__file__).parent.parent)  # 移动到项目目录.
KEY = toml.load(KEY_FILE)['key'].encode('utf-8')
IV = toml.load(KEY_FILE)['iv'].encode('utf-8')
if len(KEY) != 32:
    raise ValueError('Key must be 32 bytes long')
if len(IV) != 16:
    raise ValueError('IV must be 16 bytes long')

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class Command:
    """
    一个 Command json 格式就像: `{"type": command_type, "args": ...}`.
    返回值就像: `{"retcode": RETCODE, content: ...}`.
    """
    POST_TOKEN = 'post_token'
    POST_ROOM = 'post_room'
    GET_DEGREE = 'get_degree'
    FETCH_DEGREE_FILE = 'fetch_degree_file'


class RetCode:
    Ok = 0
    ErrUnknown = 1
    ErrArgs = 2
    ErrNoFile = 3
