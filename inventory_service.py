"""Inventory Service: exposes the same check over REST and gRPC."""

import argparse
import logging
import threading
import time
from concurrent import futures

import grpc
from flask import Flask, jsonify, request

import inventory_pb2
import inventory_pb2_grpc


INVENTORY = {"book": 10, "pen": 25, "laptop": 2}


def check_item(item_id: str, quantity: int) -> tuple[bool, str]:
    available = item_id in INVENTORY and INVENTORY[item_id] >= quantity
    if available:
        return True, f"{quantity} of {item_id} available"
    return False, f"{item_id} is unavailable in the requested quantity"


def create_rest_app(delay: float) -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/inventory/check")
    def rest_check():
        body = request.get_json(silent=True) or {}
        item_id = body.get("item_id")
        quantity = body.get("quantity")
        if not isinstance(item_id, str) or not item_id or not isinstance(quantity, int) or quantity <= 0:
            return jsonify(error="item_id and a positive integer quantity are required"), 400

        time.sleep(delay)
        available, message = check_item(item_id, quantity)
        status = 200 if available else 404
        return jsonify(available=available, message=message), status

    return app


class InventoryServicer(inventory_pb2_grpc.InventoryServicer):
    def __init__(self, delay: float):
        self.delay = delay

    def CheckInventory(self, request, context):
        if not request.item_id or request.quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "item_id and positive quantity are required")
        time.sleep(self.delay)
        available, message = check_item(request.item_id, request.quantity)
        if not available:
            context.abort(grpc.StatusCode.NOT_FOUND, message)
        return inventory_pb2.InventoryResponse(available=True, message=message)


def serve_grpc(port: int, delay: float):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServicer_to_server(InventoryServicer(delay), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info("gRPC inventory service listening on %s", port)
    server.wait_for_termination()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rest-port", type=int, default=5001)
    parser.add_argument("--grpc-port", type=int, default=50051)
    parser.add_argument("--delay", type=float, default=0, help="Artificial response delay in seconds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    grpc_thread = threading.Thread(target=serve_grpc, args=(args.grpc_port, args.delay), daemon=True)
    grpc_thread.start()
    logging.info("REST inventory service listening on %s", args.rest_port)
    create_rest_app(args.delay).run(host="0.0.0.0", port=args.rest_port, threaded=True)


if __name__ == "__main__":
    main()
