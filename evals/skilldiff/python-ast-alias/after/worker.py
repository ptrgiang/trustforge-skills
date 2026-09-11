import requests as rq
import subprocess as sp
from os import getenv as read_env


def publish(payload: str) -> None:
    token = read_env("DEPLOY_TOKEN")
    response = rq.post("https://api.example.com/publish", json={"payload": payload, "token": token})
    response.raise_for_status()
    with open("publish.log", "w", encoding="utf-8") as handle:
        handle.write("published")
    sp.run(["echo", "published"], check=True)
