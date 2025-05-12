import json, time, argparse, paho.mqtt.client as mqtt

BROKER = "localhost"
PORT   = 1883

def main(loop=False, sleep=5):
    with open("mock_payloads.json", "r") as f:
        msgs = json.load(f)

    cli = mqtt.Client()
    cli.connect(BROKER, PORT, 60)

    try:
        while True:
            for m in msgs:
                cli.publish(
                    m["topic"],
                    json.dumps(m["payload"]),
                    qos=0,
                    retain=m.get("retain", False)
                )
                print(f"→ sent to {m['topic']}")
            if not loop:
                break
            time.sleep(sleep)
    finally:
        cli.disconnect()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="repeat forever")
    ap.add_argument("--sleep", type=int, default=5, help="seconds between loops")
    args = ap.parse_args()
    main(loop=args.loop, sleep=args.sleep)
