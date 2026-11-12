from __future__ import annotations

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urljoin

import requests

from core.settings import settings

log = logging.getLogger("Viviane.SmartHome")

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SmartDevice:
    id: str
    name: str
    type: str  # light, switch, sensor, climate, cover, media_player, lock, fan, vacuum
    room: str = ""
    state: dict = field(default_factory=dict)
    attributes: dict = field(default_factory=dict)
    available: bool = True
    protocol: str = "unknown"  # homeassistant, mqtt, tuya, shelly, hue, matter

    def is_on(self) -> bool:
        return self.state.get("state", "").lower() in ("on", "open", "true", "home", "playing")

    def get_brightness(self) -> Optional[int]:
        return self.state.get("brightness") or self.attributes.get("brightness")

    def get_color_temp(self) -> Optional[int]:
        return self.state.get("color_temp") or self.attributes.get("color_temp")

    def get_temperature(self) -> Optional[float]:
        return self.state.get("temperature") or self.attributes.get("current_temperature")

    def get_humidity(self) -> Optional[float]:
        return self.attributes.get("humidity")

@dataclass
class Automation:
    id: str
    name: str
    trigger: dict  # {type: state_change/time/sun/event, entity_id, ...}
    conditions: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    enabled: bool = True
    last_run: Optional[float] = None

# ============================================================================
# Base Protocol Adapter
# ============================================================================

class ProtocolAdapter(ABC):
    @abstractmethod
    def connect(self) -> bool: ...
    @abstractmethod
    def disconnect(self) -> None: ...
    @abstractmethod
    def get_devices(self) -> list[SmartDevice]: ...
    @abstractmethod
    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool: ...
    @abstractmethod
    def subscribe_events(self, callback: Callable) -> None: ...

# ============================================================================
# Home Assistant Adapter
# ============================================================================

class HomeAssistantAdapter(ProtocolAdapter):
    def __init__(self, url: str, token: str):
        self.base_url = url.rstrip("/") + "/api/"
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._ws = None
        self._ws_thread = None
        self._event_callback = None

    def connect(self) -> bool:
        try:
            r = requests.get(urljoin(self.base_url, "states"), headers=self.headers, timeout=5)
            if r.status_code == 200:
                self._start_websocket()
                return True
        except Exception as e:
            log.error(f"HA connection failed: {e}")
        return False

    def _start_websocket(self):
        try:
            import websocket
            ws_url = self.base_url.replace("http", "ws") + "websocket"
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
            )
            self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            self._ws_thread.start()
        except Exception as e:
            log.warning(f"HA WebSocket not available: {e}")

    def _on_ws_open(self, ws):
        ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("type") == "event" and self._event_callback:
                event = data["event"]
                if event["event_type"] == "state_changed":
                    self._event_callback(event["data"])
        except Exception:
            pass

    def _on_ws_error(self, ws, error):
        log.debug(f"HA WS error: {error}")

    def _on_ws_close(self, ws, code, reason):
        log.debug("HA WS closed")
        time.sleep(5)
        self._start_websocket()

    def get_devices(self) -> list[SmartDevice]:
        try:
            r = requests.get(urljoin(self.base_url, "states"), headers=self.headers, timeout=10)
            devices = []
            for ent in r.json():
                domain = ent["entity_id"].split(".")[0]
                if domain in ("light", "switch", "sensor", "climate", "cover", "media_player", "lock", "fan", "vacuum", "binary_sensor"):
                    devices.append(SmartDevice(
                        id=ent["entity_id"],
                        name=ent.get("attributes", {}).get("friendly_name", ent["entity_id"]),
                        type=domain,
                        room=ent.get("attributes", {}).get("area_id", ""),
                        state={"state": ent["state"]},
                        attributes=ent.get("attributes", {}),
                        available=ent["state"] != "unavailable",
                        protocol="homeassistant"
                    ))
            return devices
        except Exception as e:
            log.error(f"HA get_devices failed: {e}")
            return []

    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool:
        try:
            data = {"entity_id": entity_id, **kwargs}
            r = requests.post(
                urljoin(self.base_url, f"services/{domain}/{service}"),
                headers=self.headers,
                json=data,
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            log.error(f"HA call_service failed: {e}")
            return False

    def subscribe_events(self, callback: Callable) -> None:
        self._event_callback = callback

    def disconnect(self) -> None:
        if self._ws:
            self._ws.close()

# ============================================================================
# MQTT Adapter
# ============================================================================

class MQTTAdapter(ProtocolAdapter):
    def __init__(self, host: str, port: int = 1883, username: str = "", password: str = "", prefix: str = "homeassistant"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.prefix = prefix
        self._client = None
        self._devices = {}
        self._event_callback = None

    def connect(self) -> bool:
        try:
            import paho.mqtt.client as mqtt
            self._client = mqtt.Client()
            if self.username:
                self._client.username_pw_set(self.username, self.password)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.connect(self.host, self.port, 60)
            self._client.loop_start()
            return True
        except Exception as e:
            log.error(f"MQTT connection failed: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(f"{self.prefix}/+/+/state")
            client.subscribe(f"{self.prefix}/+/+/set")
            log.info("MQTT connected")
        else:
            log.error(f"MQTT connection failed: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) >= 4:
                domain = topic_parts[1]
                device_id = topic_parts[2]
                payload = msg.payload.decode()
                if self._event_callback:
                    self._event_callback({"entity_id": f"{domain}.{device_id}", "new_state": {"state": payload}})
        except Exception:
            pass

    def get_devices(self) -> list[SmartDevice]:
        return list(self._devices.values())

    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool:
        if not self._client:
            return False
        try:
            parts = entity_id.split(".")
            if len(parts) == 2:
                topic = f"{self.prefix}/{parts[0]}/{parts[1]}/set"
                self._client.publish(topic, json.dumps(kwargs))
                return True
        except Exception as e:
            log.error(f"MQTT call_service failed: {e}")
        return False

    def subscribe_events(self, callback: Callable) -> None:
        self._event_callback = callback

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

# ============================================================================
# Tuya Adapter (via TinyTuya)
# ============================================================================

class TuyaAdapter(ProtocolAdapter):
    def __init__(self):
        self._devices = {}
        self._tuya = None

    def connect(self) -> bool:
        try:
            import tinytuya
            self._tuya = tinytuya
            # Devices need to be configured with device_id, ip, local_key
            return True
        except ImportError:
            log.warning("tinytuya not installed")
            return False

    def add_device(self, device_id: str, ip: str, local_key: str, name: str, type_: str, room: str = ""):
        if self._tuya:
            d = self._tuya.Device(device_id, ip, local_key)
            self._devices[device_id] = SmartDevice(
                id=device_id, name=name, type=type_, room=room,
                attributes={"ip": ip, "local_key": local_key}, protocol="tuya"
            )

    def get_devices(self) -> list[SmartDevice]:
        for dev_id, dev in self._devices.items():
            try:
                status = self._tuya.Device(dev.attributes["ip"], dev.id, dev.attributes["local_key"]).status()
                dev.state = {"state": "on" if status.get("dps", {}).get("1") else "off"}
                dev.available = True
            except Exception:
                dev.available = False
        return list(self._devices.values())

    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool:
        dev = self._devices.get(entity_id)
        if not dev or not self._tuya:
            return False
        try:
            d = self._tuya.Device(dev.attributes["ip"], dev.id, dev.attributes["local_key"])
            if service == "turn_on":
                d.set_value(1, True)
            elif service == "turn_off":
                d.set_value(1, False)
            return True
        except Exception as e:
            log.error(f"Tuya call_service failed: {e}")
        return False

    def subscribe_events(self, callback: Callable) -> None:
        pass  # Polling-based

    def disconnect(self) -> None:
        pass

# ============================================================================
# Shelly Adapter
# ============================================================================

class ShellyAdapter(ProtocolAdapter):
    def __init__(self):
        self._devices = {}

    def connect(self) -> bool:
        return True

    def add_device(self, ip: str, name: str, type_: str, room: str = "", auth_key: str = ""):
        self._devices[ip] = SmartDevice(
            id=ip, name=name, type=type_, room=room,
            attributes={"ip": ip, "auth_key": auth_key}, protocol="shelly"
        )

    def get_devices(self) -> list[SmartDevice]:
        for ip, dev in self._devices.items():
            try:
                r = requests.get(f"http://{ip}/rpc/Shelly.GetStatus", timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    dev.state = {"state": "on" if data.get("switch:0", {}).get("output") else "off"}
                    dev.available = True
            except Exception:
                dev.available = False
        return list(self._devices.values())

    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool:
        dev = self._devices.get(entity_id)
        if not dev:
            return False
        try:
            ip = dev.attributes["ip"]
            if service == "turn_on":
                requests.post(f"http://{ip}/rpc/Switch.Set", json={"id": 0, "on": True}, timeout=3)
            elif service == "turn_off":
                requests.post(f"http://{ip}/rpc/Switch.Set", json={"id": 0, "on": False}, timeout=3)
            return True
        except Exception as e:
            log.error(f"Shelly call_service failed: {e}")
        return False

    def subscribe_events(self, callback: Callable) -> None:
        pass

    def disconnect(self) -> None:
        pass

# ============================================================================
# Philips Hue Adapter
# ============================================================================

class HueAdapter(ProtocolAdapter):
    def __init__(self, bridge_ip: str, username: str = ""):
        self.bridge_ip = bridge_ip
        self.username = username
        self._lights = {}

    def connect(self) -> bool:
        try:
            r = requests.get(f"http://{self.bridge_ip}/api/{self.username}/lights", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def get_devices(self) -> list[SmartDevice]:
        try:
            r = requests.get(f"http://{self.bridge_ip}/api/{self.username}/lights", timeout=5)
            devices = []
            for lid, ldata in r.json().items():
                devices.append(SmartDevice(
                    id=f"light.hue_{lid}",
                    name=ldata["name"],
                    type="light",
                    room=ldata.get("room", ""),
                    state={"state": "on" if ldata["state"]["on"] else "off", "brightness": ldata["state"]["bri"]},
                    attributes=ldata["state"],
                    available=ldata["state"]["reachable"],
                    protocol="hue"
                ))
            self._lights = {d.id: d for d in devices}
            return devices
        except Exception as e:
            log.error(f"Hue get_devices failed: {e}")
            return []

    def call_service(self, domain: str, service: str, entity_id: str, **kwargs) -> bool:
        lid = entity_id.split("_")[-1]
        if not lid.isdigit():
            return False
        try:
            data = {}
            if service == "turn_on":
                data["on"] = True
            elif service == "turn_off":
                data["on"] = False
            if "brightness" in kwargs:
                data["bri"] = kwargs["brightness"]
            if "color_temp" in kwargs:
                data["ct"] = kwargs["color_temp"]
            r = requests.put(
                f"http://{self.bridge_ip}/api/{self.username}/lights/{lid}/state",
                json=data, timeout=3
            )
            return r.status_code == 200
        except Exception as e:
            log.error(f"Hue call_service failed: {e}")
        return False

    def subscribe_events(self, callback: Callable) -> None:
        pass

    def disconnect(self) -> None:
        pass

# ============================================================================
# Smart Home Manager
# ============================================================================

class SmartHomeManager:
    def __init__(self):
        self.adapters: list[ProtocolAdapter] = []
        self.devices: dict[str, SmartDevice] = {}
        self.automations: dict[str, Automation] = {}
        self._running = False
        self._update_thread = None
        self._event_callbacks: list[Callable] = []

    def add_adapter(self, adapter: ProtocolAdapter) -> bool:
        if adapter.connect():
            self.adapters.append(adapter)
            adapter.subscribe_events(self._on_device_event)
            self._refresh_devices()
            log.info(f"Adapter connected: {type(adapter).__name__}")
            return True
        return False

    def _refresh_devices(self):
        for adapter in self.adapters:
            for dev in adapter.get_devices():
                self.devices[dev.id] = dev
        log.info(f"Total devices: {len(self.devices)}")

    def _on_device_event(self, event_data: dict):
        entity_id = event_data.get("entity_id")
        new_state = event_data.get("new_state", {})
        if entity_id in self.devices:
            self.devices[entity_id].state = new_state
            self.devices[entity_id].available = True
            for cb in self._event_callbacks:
                try:
                    cb(self.devices[entity_id])
                except Exception:
                    pass

    def subscribe_events(self, callback: Callable):
        self._event_callbacks.append(callback)

    def get_devices(self, type_: str = "", room: str = "") -> list[SmartDevice]:
        result = list(self.devices.values())
        if type_:
            result = [d for d in result if d.type == type_]
        if room:
            result = [d for d in result if d.room.lower() == room.lower()]
        return result

    def get_device(self, entity_id: str) -> Optional[SmartDevice]:
        return self.devices.get(entity_id)

    def turn_on(self, entity_id: str, **kwargs) -> bool:
        dev = self.devices.get(entity_id)
        if not dev:
            return False
        for adapter in self.adapters:
            if adapter.call_service(dev.type, "turn_on", entity_id, **kwargs):
                dev.state["state"] = "on"
                return True
        return False

    def turn_off(self, entity_id: str) -> bool:
        dev = self.devices.get(entity_id)
        if not dev:
            return False
        for adapter in self.adapters:
            if adapter.call_service(dev.type, "turn_off", entity_id):
                dev.state["state"] = "off"
                return True
        return False

    def set_brightness(self, entity_id: str, brightness: int) -> bool:
        dev = self.devices.get(entity_id)
        if not dev or dev.type != "light":
            return False
        for adapter in self.adapters:
            if adapter.call_service(dev.type, "turn_on", entity_id, brightness=brightness):
                dev.state["brightness"] = brightness
                dev.state["state"] = "on"
                return True
        return False

    def set_color_temp(self, entity_id: str, color_temp: int) -> bool:
        dev = self.devices.get(entity_id)
        if not dev or dev.type != "light":
            return False
        for adapter in self.adapters:
            if adapter.call_service(dev.type, "turn_on", entity_id, color_temp=color_temp):
                dev.attributes["color_temp"] = color_temp
                return True
        return False

    def set_climate_temp(self, entity_id: str, temperature: float) -> bool:
        dev = self.devices.get(entity_id)
        if not dev or dev.type != "climate":
            return False
        for adapter in self.adapters:
            if adapter.call_service("climate", "set_temperature", entity_id, temperature=temperature):
                dev.attributes["temperature"] = temperature
                return True
        return False

    def open_cover(self, entity_id: str) -> bool:
        dev = self.devices.get(entity_id)
        if not dev or dev.type != "cover":
            return False
        for adapter in self.adapters:
            if adapter.call_service("cover", "open_cover", entity_id):
                dev.state["state"] = "open"
                return True
        return False

    def close_cover(self, entity_id: str) -> bool:
        dev = self.devices.get(entity_id)
        if not dev or dev.type != "cover":
            return False
        for adapter in self.adapters:
            if adapter.call_service("cover", "close_cover", entity_id):
                dev.state["state"] = "closed"
                return True
        return False

    def add_automation(self, automation: Automation):
        self.automations[automation.id] = automation

    def remove_automation(self, automation_id: str):
        self.automations.pop(automation_id, None)

    def start(self):
        self._running = True
        self._update_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._update_thread.start()

    def stop(self):
        self._running = False
        for adapter in self.adapters:
            adapter.disconnect()

    def _run_loop(self):
        while self._running:
            self._check_automations()
            time.sleep(10)

    def _check_automations(self):
        for auto in self.automations.values():
            if not auto.enabled:
                continue
            # Simple state change trigger
            if auto.trigger.get("type") == "state_change":
                entity_id = auto.trigger.get("entity_id")
                target_state = auto.trigger.get("state")
                dev = self.devices.get(entity_id)
                if dev and dev.state.get("state") == target_state:
                    if self._check_conditions(auto.conditions):
                        self._execute_actions(auto.actions)
                        auto.last_run = time.time()

    def _check_conditions(self, conditions: list) -> bool:
        for cond in conditions:
            entity_id = cond.get("entity_id")
            state = cond.get("state")
            dev = self.devices.get(entity_id)
            if not dev or dev.state.get("state") != state:
                return False
        return True

    def _execute_actions(self, actions: list):
        for action in actions:
            action_type = action.get("type")
            entity_id = action.get("entity_id")
            if action_type == "turn_on":
                self.turn_on(entity_id, **action.get("params", {}))
            elif action_type == "turn_off":
                self.turn_off(entity_id)
            elif action_type == "set_brightness":
                self.set_brightness(entity_id, action.get("brightness", 255))
            elif action_type == "notify":
                # Would integrate with notification system
                pass


# Global instance
smarthome = SmartHomeManager()

# ============================================================================
# Configuration Helper
# ============================================================================

def configure_from_env() -> SmartHomeManager:
    """Configura adapters baseado em variáveis de ambiente."""
    import os

    # Home Assistant
    ha_url = os.getenv("HOMEASSISTANT_URL")
    ha_token = os.getenv("HOMEASSISTANT_TOKEN")
    if ha_url and ha_token:
        smarthome.add_adapter(HomeAssistantAdapter(ha_url, ha_token))

    # MQTT
    mqtt_host = os.getenv("MQTT_HOST")
    if mqtt_host:
        smarthome.add_adapter(MQTTAdapter(
            host=mqtt_host,
            port=int(os.getenv("MQTT_PORT", "1883")),
            username=os.getenv("MQTT_USER", ""),
            password=os.getenv("MQTT_PASS", ""),
        ))

    # Philips Hue
    hue_ip = os.getenv("HUE_BRIDGE_IP")
    hue_user = os.getenv("HUE_USERNAME")
    if hue_ip and hue_user:
        smarthome.add_adapter(HueAdapter(hue_ip, hue_user))

    # Shelly
    shelly_ips = os.getenv("SHELLY_IPS", "").split(",")
    for ip in shelly_ips:
        ip = ip.strip()
        if ip:
            adapter = ShellyAdapter()
            adapter.add_device(ip, f"Shelly {ip}", "switch")
            smarthome.add_adapter(adapter)

    # Tuya
    tuya_devices = os.getenv("TUYA_DEVICES", "")
    if tuya_devices:
        adapter = TuyaAdapter()
        for entry in tuya_devices.split(";"):
            parts = entry.split(",")
            if len(parts) >= 4:
                adapter.add_device(parts[0], parts[1], parts[2], parts[3], parts[4] if len(parts) > 4 else "switch")
        smarthome.add_adapter(adapter)

    return smarthome