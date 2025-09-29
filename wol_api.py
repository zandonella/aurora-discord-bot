from flask import Flask, jsonify
from wakeonlan import send_magic_packet
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

MAC_ADDRESS = os.getenv("MAC_ADDRESS")
WOL_API_PORT = int(os.getenv("WOL_API_PORT", 8000))
WOL_API_IP = os.getenv("WOL_API_IP")


@app.route("/wake", methods=["POST"])
def wake():
    try:
        send_magic_packet(MAC_ADDRESS)
        return jsonify({"status": "ok", "message": "Magic packet sent."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host=WOL_API_IP, port=WOL_API_PORT)
