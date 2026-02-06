import os
import platform
import sys

from ...utils import vdf

operating_system = platform.system()

if operating_system == ("Linux" or "Darwin"):
    steamdir = os.getenv("HOME") + "/.local/share/Steam/"
elif operating_system == "Windows":
    steamdir = "C:/Program Files (x86)/Steam/"
else:
    sys.exit(f"Cannot handle operating system: {operating_system}")


def GetSteamId():
    d = vdf.parse(open("{0}config/loginusers.vdf".format(steamdir), encoding="utf-8"))
    users = d["users"]
    for id64 in users:
        if users[id64]["MostRecent"] == "1":
            return int(id64)


def GetAccountId():
    return GetSteamId() & 0xFFFFFFFF
