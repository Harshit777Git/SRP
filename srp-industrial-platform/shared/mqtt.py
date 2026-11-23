import os
from pathlib import Path

import paho.mqtt.client as mqtt


def client(client_id, persistent=False):
    connection = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                             protocol=mqtt.MQTTv311, clean_session=not persistent)
    if os.getenv("MQTT_TLS") == "1":
        connection.tls_set(ca_certs=os.getenv("MQTT_CA") or None)
    if os.getenv("MQTT_USERNAME"):
        password_path = os.getenv("MQTT_PASSWORD_FILE")
        password = Path(password_path).read_text().strip() if password_path else os.getenv("MQTT_PASSWORD")
        connection.username_pw_set(os.environ["MQTT_USERNAME"], password)
    connection.reconnect_delay_set(1, 10)
    return connection


def connect(connection):
    connection.connect_async(os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", "1883")), 20)
    connection.loop_start()


def qos():
    value = int(os.getenv("MQTT_QOS", "1"))
    if value not in (0,1,2):
        raise ValueError("MQTT_QOS must be 0, 1 or 2")
    return value
