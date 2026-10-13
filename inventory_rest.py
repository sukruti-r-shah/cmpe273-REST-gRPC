"""Inventory Service REST/HTTP implementation."""

import argparse
import time

from flask import Flask, jsonify, request


INVENTORY = {"book": 10, "pen": 25, "laptop": 2}


def create_app(delay: float) -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/inventory/check")
    def check_inventory():
        body = request.get_json(silent=True) or {}
        item_id = body.get("item_id")
        quantity = body.get("quantity")
        if not isinstance(item_id, str) or not item_id or not isinstance(quantity, int) or quantity <= 0:
            return jsonify(error="item_id and a positive integer quantity are required"), 400

        time.sleep(delay)
        available = item_id in INVENTORY and INVENTORY[item_id] >= quantity
        message = (
            f"{quantity} of {item_id} available"
            if available
            else f"{item_id} is unavailable in the requested quantity"
        )
        return jsonify(available=available, message=message), 200 if available else 404

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--delay", type=float, default=0, help="Artificial response delay in seconds")
    args = parser.parse_args()
    create_app(args.delay).run(host="0.0.0.0", port=args.port, threaded=True)
