# CMPE 273 – Order + Inventory over REST and gRPC

Two small Python services. The Order Service takes an order and asks the Inventory Service whether the item is in stock. It can make that call over plain REST or over gRPC, and both do the same thing, so it's easy to compare them side by side.

The Inventory Service runs both servers at once: REST on port 5001 and gRPC on port 50051. The stock is hard-coded (`book: 10`, `pen: 25`, `laptop: 2`).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The generated gRPC files (`inventory_pb2.py`, `inventory_pb2_grpc.py`) are already committed. If you change `proto/inventory.proto`, regenerate them with:

```bash
python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/inventory.proto
```

> **Mac users:** port 5000 is taken by AirPlay Receiver, and you'll get a confusing `403 Forbidden` back. Either turn AirPlay Receiver off in System Settings, or start the Order Service with `--port 5050` and use 5050 in the curl commands below.

## Running the REST version

Open two terminals in the project folder.

```bash
# terminal 1
python inventory_service.py

# terminal 2
python order_service.py
```

Then place an order through the REST path:

```bash
curl -i -X POST http://localhost:5000/orders/rest \
  -H 'Content-Type: application/json' \
  -d '{"item_id":"book","quantity":2}'
```

```text
HTTP/1.1 200 OK
{"available":true,"message":"2 of book available"}
```

## Running the gRPC version

It's the same two processes. Just hit the `/orders/grpc` route instead, and the Order Service will use the generated `InventoryStub` to talk to the Inventory Service:

```bash
curl -i -X POST http://localhost:5000/orders/grpc \
  -H 'Content-Type: application/json' \
  -d '{"item_id":"book","quantity":2}'
```

```text
HTTP/1.1 200 OK
{"available":true,"message":"2 of book available"}
```

That response is still JSON, because the gRPC call happens between the two services. To see a raw gRPC request and response, call the Inventory Service directly with the small client script:

```bash
python grpc_client.py book 2
```

```text
available: true
message: "2 of book available"
```

With the 5-second delay from the next section, the same script shows the deadline failing on its own:

```text
$ python grpc_client.py book 2
DEADLINE_EXCEEDED: Deadline Exceeded
```

If you ask for more than is in stock (e.g. 9 laptops), the Order Service returns `409`. Internally, REST signals this with a `404` and gRPC with `NOT_FOUND`.

## Testing timeouts and deadlines

The Order Service waits at most 2 seconds for the Inventory Service. For REST that's `requests.post(..., timeout=2.0)`, and for gRPC it's `timeout=2.0` on the stub call, which sets the deadline. To trigger them, I restarted the Inventory Service with a 5-second artificial delay:

```bash
# terminal 1: Ctrl+C, then
python inventory_service.py --delay 5
```

Then I ran both curl commands from above again, leaving the Order Service running.

REST timed out:

```text
HTTP/1.1 504 GATEWAY TIMEOUT
{"error":"inventory service timed out"}
```

gRPC hit its deadline:

```text
HTTP/1.1 504 GATEWAY TIMEOUT
{"error":"inventory service deadline exceeded"}
```

The Order Service logged both failures and kept going:

```text
WARNING REST inventory request exceeded 2.00s timeout
WARNING gRPC inventory request exceeded 2.00s deadline
```

To show it was still alive afterwards, I checked its health endpoint:

```text
$ curl -i http://localhost:5000/health
HTTP/1.1 200 OK
{"status":"ok"}
```

## REST vs gRPC: what I noticed

REST was quicker to get going: I could test everything with curl and read the JSON directly. The downside was writing the input validation myself and translating HTTP status codes (like a `404` from inventory) into something meaningful for the order. gRPC needed more setup up front, with the `.proto` file and generating stubs, but after that the request and response types were enforced for me and errors came back as clear status codes like `NOT_FOUND` and `DEADLINE_EXCEEDED`. Timeouts were handled differently too: REST sets them on the HTTP client, while gRPC passes a deadline with each call. For something people or browsers call directly I'd pick REST, but for one service talking to another, gRPC felt cleaner.

## Files

```text
proto/inventory.proto       the gRPC contract
inventory_service.py        Inventory Service (REST + gRPC servers)
order_service.py            Order Service (REST API, calls inventory via REST or gRPC)
grpc_client.py              tiny client for calling the gRPC server directly
inventory_pb2*.py           generated from the .proto
requirements.txt
```
