"""Calls the Inventory Service's gRPC server directly."""

import argparse

import grpc

import inventory_pb2
import inventory_pb2_grpc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("item_id", nargs="?", default="book")
    parser.add_argument("quantity", nargs="?", type=int, default=2)
    parser.add_argument("--target", default="localhost:50051")
    parser.add_argument("--timeout", type=float, default=2.0, help="gRPC deadline in seconds")
    args = parser.parse_args()

    with grpc.insecure_channel(args.target) as channel:
        stub = inventory_pb2_grpc.InventoryStub(channel)
        try:
            response = stub.CheckInventory(
                inventory_pb2.InventoryRequest(item_id=args.item_id, quantity=args.quantity),
                timeout=args.timeout,
            )
        except grpc.RpcError as exc:
            print(f"{exc.code().name}: {exc.details()}")
            raise SystemExit(1)
    print(response, end="")


if __name__ == "__main__":
    main()
