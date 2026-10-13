# REST and gRPC service interaction

This small Python app has an Order Service and an Inventory Service. The Order Service checks inventory using either REST/HTTP or gRPC. Both paths implement the same operation.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/inventory.proto
```

The last command generates `inventory_pb2.py` and `inventory_pb2_grpc.py` from the contract.

## Run the REST version

Use two terminals, from the project directory.

```bash
# Terminal 1: Inventory REST Service (:5001)
python inventory_rest.py

# Terminal 2: Inventory gRPC Service (:50051)
python inventory_grpc.py

# Terminal 3: Order Service (:5000)
python order_service.py
```

Check an available item over REST:

```bash
curl -i -X POST http://localhost:5000/orders/rest \
  -H 'Content-Type: application/json' \
  -d '{"item_id":"book","quantity":2}'
```

Successful REST response:

```text
HTTP/1.1 200 OK
{"available":true,"message":"2 of book available"}
```

## Run the gRPC version

The same two processes provide the gRPC version. The Order Service route below makes its downstream call using the generated `InventoryStub` and a gRPC deadline:

```bash
curl -i -X POST http://localhost:5000/orders/grpc \
  -H 'Content-Type: application/json' \
  -d '{"item_id":"book","quantity":2}'
```

Successful gRPC response through the Order Service:

```text
HTTP/1.1 200 OK
{"available":true,"message":"2 of book available"}
```

For a direct gRPC request to the Inventory Service, use the generated client classes:

```bash
python - <<'PY'
import grpc
import inventory_pb2
import inventory_pb2_grpc

with grpc.insecure_channel("localhost:50051") as channel:
    result = inventory_pb2_grpc.InventoryStub(channel).CheckInventory(
        inventory_pb2.InventoryRequest(item_id="book", quantity=2), timeout=2
    )
    print(result)
PY
```

Example direct gRPC response:

```text
available: true
message: "2 of book available"
```

An unavailable item produces HTTP `409` from the Order Service. The Inventory Service uses REST `404` and gRPC `NOT_FOUND` internally.

## Evidence: timeout and deadline handling

Stop both Inventory services and restart them with a 5-second artificial delay. The Order Service timeout/deadline remains 2 seconds:

```bash
python inventory_rest.py --delay 5
python inventory_grpc.py --delay 5
```

Now run either request again. Both return HTTP `504`, but the Order Service remains running and can accept later requests:

- REST: `inventory service timed out`
- gRPC: `inventory service deadline exceeded`

Observed REST timeout output:

```text
HTTP/1.1 504 GATEWAY TIMEOUT
{"error":"inventory service timed out"}
```

Observed gRPC deadline output:

```text
HTTP/1.1 504 GATEWAY TIMEOUT
{"error":"inventory service deadline exceeded"}
```

Evidence that the Order Service remained running after both failures:

```text
$ curl -i http://localhost:5000/health
HTTP/1.1 200 OK
{"status":"ok"}
```

The timeout is set on `requests.post(..., timeout=2.0)` and the deadline is set on the gRPC stub call with `timeout=2.0`.

## REST versus gRPC comparison

REST was straightforward to inspect and test because requests and responses were plain JSON over familiar HTTP endpoints. It required explicit JSON validation and mapping downstream HTTP statuses such as `404` into an Order Service response. gRPC required a `.proto` contract and generated Python stubs, but it provided typed messages and standard statuses such as `NOT_FOUND` and `DEADLINE_EXCEEDED`. The REST timeout is configured on the HTTP client, while the gRPC deadline is passed directly to the stub call. For this small service, REST is simpler for human-facing interoperability, while gRPC is more structured for service-to-service communication.

## Project layout

```text
proto/inventory.proto   gRPC service contract
inventory_rest.py       Inventory REST server
inventory_grpc.py       Inventory gRPC server
order_service.py        Order REST API and REST/gRPC clients
requirements.txt        Python dependencies
```
