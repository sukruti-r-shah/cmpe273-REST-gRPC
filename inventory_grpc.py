"""Inventory Service gRPC implementation."""

import argparse
import logging
import time
from concurrent import futures

import grpc

import inventory_pb2
import inventory_pb2_grpc


INVENTORY = {"book": 10, "pen": 25, "laptop": 2}


class InventoryServicer(inventory_pb2_grpc.InventoryServicer):
    def __init__(self, delay: float):
        self.delay = delay

    def CheckInventory(self, request, context):
        if not request.item_id or request.quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "item_id and positive quantity are required")
        time.sleep(self.delay)
        available = request.item_id in INVENTORY and INVENTORY[request.item_id] >= request.quantity
        if not available:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"{request.item_id} is unavailable in the requested quantity",
            )
        return inventory_pb2.InventoryResponse(
            available=True,
            message=f"{request.quantity} of {request.item_id} available",
        )


def serve(port: int, delay: float):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServicer_to_server(InventoryServicer(delay), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info("gRPC inventory service listening on %s", port)
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--delay", type=float, default=0, help="Artificial response delay in seconds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    serve(args.port, args.delay)
