#!/usr/bin/env python3

import asyncio
import websockets
import json
import time
import traceback
import requests
import logging

# Konfigurationsparameter
filter_uuid_import = [] # import
filter_uuid_export = [] # export
uri = [] #"ws://volkszaehler:8082/socket"  # Ersetze dies mit der tatsächlichen URI des Volkszähler Push Servers
rest_url = "http://10.0.0.221/rest"  # URL zur Abfrage der Wärmepumpenleistung

# Variablen zum Abfragen aller benötigten Leistungen
value_export = None
value_import = None
value_wp = 0

# Variablen zum Verfolgen des letzten Empfangs
last_received_export = None
last_received_import = None

disconnect = True

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VolkszaehlerClient")

# Funktion zur Verarbeitung empfangener Nachrichten
async def handle_message(message):
    global value_export, value_import, last_received_export, last_received_import, disconnet
    data = json.loads(message)
    logger.debug(f"Received message: {data}")

    if "data" in data:
        uuid = data["data"]["uuid"]
        value = data["data"]["tuples"][0][1]
        if uuid == filter_uuid_export:
            value_export = value
            last_received_export = time.time()
            logger.debug(f"Received value for export UUID {filter_uuid_export}: {value_export}")
        elif uuid == filter_uuid_import:
            value_import = value
            last_received_import = time.time()
            logger.debug(f"Received value for import UUID {filter_uuid_import}: {value_import}")

# Funktion zur Berechnung und Ausgabe der Differenz
async def calculate_difference():
    global value_export, value_import, last_received_export, last_received_import, disconnect
    while True:
        current_time = time.time()
        logger.info(f"---")

        disconnect = False
        # Setze Werte auf Null, wenn keine Daten für 60 Sekunden empfangen wurden
        if last_received_export is not None and (current_time - last_received_export) > 60:
            value_export = 0
            disconnect = True
        if last_received_import is not None and (current_time - last_received_import) > 60:
            value_import = 0
            disconnect = True

        if value_export is not None and value_import is not None:
            difference = value_import - value_export + value_wp
            logger.info(f"import power: {difference} W")
            disconnect = True
        await asyncio.sleep(1)


# Funktion zur Abfrage der Wärmepumpenleistung
async def fetch_heat_pump_power():
    global value_import, value_wp
    while True:
        try:
            response = requests.get(rest_url)
            data = response.json()
            logger.debug(f"Fetched data from REST: {data}")

            if "1.7.0" in data:
                value_wp = data["1.7.0"]
                logger.debug(f"heat pump power {value_wp}")
        except Exception as e:
            logger.error(f"Failed to fetch heat pump power: {e}")

        await asyncio.sleep(30)

# Funktion zur Wiederverbindung bei Verbindungsausfall
async def volkszaehler_client():
    init = False
    global uri
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                # Starten der Aufgaben zur Berechnung der Differenz und Abfrage der Wärmepumpenleistung
                if not init:
                    init = True
                    asyncio.create_task(calculate_difference())
                    asyncio.create_task(fetch_heat_pump_power())

                # Verarbeitung der empfangenen Nachrichten
                async for message in websocket:
                    await handle_message(message)
        except websockets.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()

        logger.info("Reconnecting in 5 seconds...")
        await asyncio.sleep(5)

def start_vz_push_receiver(ip, uuid_import, uuid_export):
    global uri, filter_uuid_import, filter_uuid_export, callback, meter
    uri = "ws://" + ip + ":8082/socket"
    filter_uuid_import = uuid_import
    filter_uuid_export = uuid_export
    logger.debug("uuid_import: " + uuid_import)
    logger.debug("uuid_export: " + uuid_export)
    logger.info("uri: " + uri)
    print('now start vz client')
    asyncio.run(volkszaehler_client())
    print('started vz client')

# Ausführung des WebSocket-Clients
if __name__ == "__main__":
    asyncio.run(volkszaehler_client())
