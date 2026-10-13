"""Order Service: checks inventory through REST or gRPC."""

import argparse
import logging

import grpc
import requests
from flask import Flask, jsonify, request

import inventory_pb2
import inventory_pb2_grpc


def create_app(inventory_rest_url: str, inventory_grpc_target: str, timeout: float) -> Flask:
    app = Flask(__name__)

    def parse_order():
        body = request.get_json(silent=True) or {}
        item_id = body.get("item_id")
        quantity = body.get("quantity")
        if not isinstance(item_id, str) or not item_id or not isinstance(quantity, int) or quantity <= 0:
            return None, (jsonify(error="item_id and a positive integer quantity are required"), 400)
        return (item_id, quantity), None

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/orders/rest")
    def order_over_rest():
        order, error = parse_order()
        if error:
            return error
        item_id, quantity = order
        try:
            response = requests.post(
                inventory_rest_url,
                json={"item_id": item_id, "quantity": quantity},
                timeout=timeout,
            )
        except requests.Timeout:
            logging.warning("REST inventory request exceeded %.2fs timeout", timeout)
            return jsonify(error="inventory service timed out"), 504
        except requests.RequestException:
            logging.exception("REST inventory request failed")
            return jsonify(error="inventory service unavailable"), 503

        if response.status_code == 404:
            return jsonify(available=False, message="requested inventory is unavailable"), 409
        if response.status_code != 200:
            return jsonify(error="inventory service returned an error"), 502
        return jsonify(available=True, message=response.json().get("message"))

    @app.post("/orders/grpc")
    def order_over_grpc():
        order, error = parse_order()
        if error:
            return error
        item_id, quantity = order
        try:
            with grpc.insecure_channel(inventory_grpc_target) as channel:
                stub = inventory_pb2_grpc.InventoryStub(channel)
                result = stub.CheckInventory(
                    inventory_pb2.InventoryRequest(item_id=item_id, quantity=quantity),
                    timeout=timeout,
                )
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return jsonify(available=False, message="requested inventory is unavailable"), 409
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                logging.warning("gRPC inventory request exceeded %.2fs deadline", timeout)
                return jsonify(error="inventory service deadline exceeded"), 504
            logging.exception("gRPC inventory request failed")
            return jsonify(error="inventory service unavailable"), 503
        return jsonify(available=result.available, message=result.message)

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--inventory-rest-url", default="http://localhost:5001/inventory/check")
    parser.add_argument("--inventory-grpc-target", default="localhost:50051")
    parser.add_argument("--timeout", type=float, default=2.0, help="REST timeout and gRPC deadline in seconds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    create_app(args.inventory_rest_url, args.inventory_grpc_target, args.timeout).run(
        host="0.0.0.0", port=args.port, threaded=True
    )


if __name__ == "__main__":
    main()
