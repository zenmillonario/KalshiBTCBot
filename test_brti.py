import websocket
import json

URL = "wss://www.cfbenchmarks.com/ws/v4"

def on_open(ws):
    print("Connected to CF Benchmarks.")
    print("Requesting connection information...")

    message = {
        "type": "info"
    }

    ws.send(json.dumps(message))

def on_message(ws, message):
    print("\nMESSAGE RECEIVED:")
    print(message)
    ws.close()

def on_error(ws, error):
    print("\nERROR:")
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("\nConnection closed.")
    print("Status:", close_status_code)
    print("Message:", close_msg)

print("Connecting to CF Benchmarks...")

ws = websocket.WebSocketApp(
    URL,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()