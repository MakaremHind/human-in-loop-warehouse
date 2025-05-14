import json, paho.mqtt.client as mqtt, time

BROKER = "192.168.50.100"
TOPIC  = "/inventory/boxes"

payload = {
    "header": {
        "timestamp": time.time(),
        "module_id": "demo",
        "correlation_id": "demo",
        "version": 1
    },
    "boxes": [
        {
            "id": 1,
            "color": "red",
            "type": "small_box",
            "global_pose": {
                "x": 10, "y": 20, "z": 0,
                "roll": 0, "pitch": 0, "yaw": 0
            }
        }
    ]
}

cli = mqtt.Client()
cli.connect(BROKER, 1883, 60)
cli.publish(TOPIC, json.dumps(payload), qos=0, retain=True)
cli.disconnect()
print("Published test box to /inventory/boxes")
