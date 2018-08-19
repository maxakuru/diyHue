import websocket
from threading import Thread
from diyhue.config import ConfigHandler

class WSClientThread(Thread):
	def __init__(self, host="127.0.0.1", port=1337, callbacks={}):
		self.alive = False

		if type(callbacks) is not dict:
			raise ValueError('Callbacks must be a dictionary of key:functions')
		
		self.set_callbacks(callbacks)

		self._host = host
		self._port = port
		self._socket = None

	def run(self):
		self.connect()

	def set_callbacks(self, callbacks):
		self.on_error = callbacks['on_error'] if ('on_error' in callbacks) else self._on_error
		self.on_message = callbacks['on_message'] if ('on_message' in callbacks) else self._on_message
		self.on_close = callbacks['on_close'] if ('on_close' in callbacks) else self._on_close
		self.on_open = callbacks['on_open'] if ('on_open' in callbacks) else self._on_open

	def connect(self):
        #websocket.enableTrace(True)
        self._socket = websocket.WebSocketApp("ws://{host}:{port}"
        			.format(host=self._host,port=self._port),
        			on_message = self.on_message,
        			on_error = self.on_error,
        			on_close = self.on_close)

        self._socket.on_open = self.on_open
        self._socket.run_forever()

    def _on_error(self, ws, message):
        self.logger.error("Error callback fired, message: %s"%message)

    def _on_close(self, ws):
        if self.alive:
            self.alive = False
            # TODO: reconnect timer
            print(("deconz websocket disconnected", code, reason))
			del bridge_config["deconz"]["websocketport"]

    def _on_message(self, ws, message):
        self.logger.info("Message from websocket server: %s"%message)

    def _on_open(self, ws):
        self.alive = True
        self._socket = ws

	def _on_message(self, m):
		print(m)
		message = json.loads(str(m))
		try:
			if message["r"] == "sensors":
				bridge_sensor_id = bridge_config["deconz"]["sensors"][message["id"]]["bridgeid"]
				if "state" in message and bridge_config["sensors"][bridge_sensor_id]["config"]["on"]:

					#change codes for emulated hue Switches
					if "hueType" in bridge_config["deconz"]["sensors"][message["id"]]:
						rewriteDict = {"ZGPSwitch": {1002: 34, 3002: 16, 4002: 17, 5002: 18}, "ZLLSwitch" : {1002 : 1000, 2002: 2000, 2001: 2001, 2003: 2002, 3001: 3001, 3002: 3000, 3003: 3002, 4002: 4000, 5002: 4000} }
						message["state"]["buttonevent"] = rewriteDict[bridge_config["deconz"]["sensors"][message["id"]]["hueType"]][message["state"]["buttonevent"]]
					#end change codes for emulated hue Switches

					#convert tradfri motion sensor notification to look like Hue Motion Sensor
					if message["state"] and bridge_config["deconz"]["sensors"][message["id"]]["modelid"] == "TRADFRI motion sensor":
						#find the light sensor id
						light_sensor = "0"
						for sensor in bridge_config["sensors"].keys():
							if bridge_config["sensors"][sensor]["type"] == "ZLLLightLevel" and bridge_config["sensors"][sensor]["uniqueid"] == bridge_config["sensors"][bridge_sensor_id]["uniqueid"][:-1] + "0":
								light_sensor = sensor
								break
						if bridge_config["deconz"]["sensors"][message["id"]]["lightsensor"] == "none":
							message["state"].update({"dark": True})
						elif bridge_config["deconz"]["sensors"][message["id"]]["lightsensor"] == "astral":
							message["state"]["dark"] = not bridge_config["sensors"]["1"]["state"]["daylight"]

						if  message["state"]["dark"]:
							bridge_config["sensors"][light_sensor]["state"]["lightlevel"] = 6000
						else:
							bridge_config["sensors"][light_sensor]["state"]["lightlevel"] = 25000
						bridge_config["sensors"][light_sensor]["state"]["dark"] = message["state"]["dark"]
						bridge_config["sensors"][light_sensor]["state"]["daylight"] = not message["state"]["dark"]
						bridge_config["sensors"][light_sensor]["state"]["lastupdated"] = message["state"]["lastupdated"]

					#Xiaomi motion w/o light level sensor
					if message["state"] and bridge_config["deconz"]["sensors"][message["id"]]["modelid"] == "lumi.sensor_motion":
						for sensor in bridge_config["sensors"].keys():
							if bridge_config["sensors"][sensor]["type"] == "ZLLLightLevel" and bridge_config["sensors"][sensor]["uniqueid"] == bridge_config["sensors"][bridge_sensor_id]["uniqueid"][:-1] + "0":
								light_sensor = sensor
								break

						if bridge_config["sensors"]["1"]["modelid"] == "PHDL00" and bridge_config["sensors"]["1"]["state"]["daylight"]:
							bridge_config["sensors"][light_sensor]["state"]["lightlevel"] = 25000
							bridge_config["sensors"][light_sensor]["state"]["dark"] = False
						else:
							bridge_config["sensors"][light_sensor]["state"]["lightlevel"] = 6000
							bridge_config["sensors"][light_sensor]["state"]["dark"] = True

					#convert xiaomi motion sensor to hue sensor
					if message["state"] and bridge_config["deconz"]["sensors"][message["id"]]["modelid"] == "lumi.sensor_motion.aq2" and message["state"] and bridge_config["deconz"]["sensors"][message["id"]]["type"] == "ZHALightLevel":
						bridge_config["sensors"][bridge_sensor_id]["state"].update(message["state"])
						return
					##############

					bridge_config["sensors"][bridge_sensor_id]["state"].update(message["state"])
					current_time = datetime.now()
					for key in message["state"].keys():
						sensors_state[bridge_sensor_id]["state"][key] = current_time
					rulesProcessor(bridge_sensor_id, current_time)
					if "buttonevent" in message["state"] and bridge_config["deconz"]["sensors"][message["id"]]["modelid"] in ["TRADFRI remote control","RWL021"]:
						if message["state"]["buttonevent"] in [2001, 3001, 4001, 5001]:
							Thread(target=longPressButton, args=[bridge_sensor_id, message["state"]["buttonevent"]]).start()
					if "presence" in message["state"] and message["state"]["presence"] and "virtual_light" in bridge_config["alarm_config"] and bridge_config["lights"][bridge_config["alarm_config"]["virtual_light"]]["state"]["on"]:
						sendEmail(bridge_config["sensors"][bridge_sensor_id]["name"])
						bridge_config["alarm_config"]["virtual_light"]
				elif "config" in message and bridge_config["sensors"][bridge_sensor_id]["config"]["on"]:
					bridge_config["sensors"][bridge_sensor_id]["config"].update(message["config"])
			elif message["r"] == "lights":
				bridge_light_id = bridge_config["deconz"]["lights"][message["id"]]["bridgeid"]
				if "state" in message:
					bridge_config["lights"][bridge_light_id]["state"].update(message["state"])
					updateGroupStats(bridge_light_id)
		except Exception as e:
			print("unable to process the request" + str(e))