FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir tuya-ipc-p2p-sdk==0.1.1

WORKDIR /app
COPY custom_components/neolight/mobile_api.py /app/mobile_api.py
COPY custom_components/neolight/panel_protocol.py /app/panel_protocol.py
COPY native_bridge/neolight_native.py /app/neolight_native.py
COPY native_bridge/account_identity.py /app/account_identity.py
COPY native_bridge/protocol.py /app/protocol.py
COPY native_bridge/avmux.py /app/avmux.py
COPY native_bridge/observe_mobile_mqtt.py /app/observe_mobile_mqtt.py
COPY native_bridge/call_signaling.py /app/call_signaling.py
COPY native_bridge/observe_call_signaling.py /app/observe_call_signaling.py

CMD ["python", "-u", "/app/neolight_native.py"]
