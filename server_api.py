from flask import Flask, jsonify, request
import json
from dotenv import load_dotenv
import os
import docker

load_dotenv()

app = Flask(__name__)

SERVERS = os.getenv("SERVERS")
SERVER_API_PORT = int(os.getenv("SERVER_API_PORT", 6000))
SERVER_API_IP = os.getenv("SERVER_API_IP")

client = docker.from_env()


def get_container(name: str):
    try:
        return client.containers.get(name)
    except docker.errors.NotFound:
        return None


def get_mc_info(container_name: str, port: int):
    try:
        container = get_container(container_name)
        if not container:
            return {
                "health": "unhealthy",
                "players": 0,
                "max_players": 0,
            }
        health = container.attrs["State"].get("Health", {}).get("Status")

        if health != "healthy":
            return {"health": health, "players": 0, "max_players": 0}

        exec_result = container.exec_run(
            cmd=f"mc-monitor status --host localhost --port {port} --json"
        )
        if exec_result.exit_code != 0:
            return {
                "health": health,
                "players": 0,
                "max_players": 0,
                "error": exec_result.output.decode(),
            }

        data = json.loads(exec_result.output.decode())
        return {
            "health": health,
            "players": data.get("players", {}).get("online", 0),
            "max_players": data.get("players", {}).get("max", 0),
        }
    except docker.errors.NotFound:
        return {"health": None, "players": 0, "max_players": 0}


def get_all_mc_status():
    statuses = {}
    for name, data in SERVERS.items():
        statuses[name] = get_mc_info(data["container"], data["port"])
    return statuses


@app.route("/status", methods=["GET"])
def status():
    return jsonify(
        {
            "server": "online",
            "services": get_all_mc_status(),
        }
    )


@app.route("/mc/status", methods=["GET"])
def mc_status():
    return jsonify(get_all_mc_status())


@app.route("/mc/start", methods=["POST"])
def mc_start():
    name = request.args.get("name")
    if name not in SERVERS:
        return jsonify({"status": "error", "message": "Unknown server"}), 400

    cont = get_container(SERVERS[name]["container"])
    if not cont:
        return jsonify({"status": "error", "message": "Container not found"}), 404

    cont.start()
    return jsonify({"status": "ok", "message": f"{name} started"})


@app.route("/mc/stop", methods=["POST"])
def mc_stop():
    name = request.args.get("name")
    if name not in SERVERS:
        return jsonify({"status": "error", "message": "Unknown server"}), 400

    cont = get_container(SERVERS[name]["container"])
    if not cont:
        return jsonify({"status": "error", "message": "Container not found"}), 404

    cont.stop()
    return jsonify({"status": "ok", "message": f"{name} stopped"})


@app.route("/mc/restart", methods=["POST"])
def mc_restart():
    name = request.args.get("name")
    if name not in SERVERS:
        return jsonify({"status": "error", "message": "Unknown server"}), 400

    cont = get_container(SERVERS[name]["container"])
    if not cont:
        return jsonify({"status": "error", "message": "Container not found"}), 404

    cont.restart()
    return jsonify({"status": "ok", "message": f"{name} restarted"})


@app.route("/pc/shutdown", methods=["POST"])
def pc_shutdown():
    os.system("sudo shutdown now")
    return jsonify({"status": "ok", "message": "Shutting down PC"})


@app.route("/pc/reboot", methods=["POST"])
def pc_reboot():
    os.system("sudo reboot")
    return jsonify({"status": "ok", "message": "Rebooting PC"})
