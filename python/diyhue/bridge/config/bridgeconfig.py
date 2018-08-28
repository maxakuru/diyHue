"""
BridgeConfig
"""

import json
import sys
from collections import defaultdict

class BridgeConfig(object):
	"""
	Loads config, handles state access, saves state to config.
	"""
	def __init__(self, filename=None, ip=None, mac=None):
		self.filename = filename
		self._state = defaultdict(lambda:defaultdict(str))
		self.load()

		self._mac = mac
		self._ip = ip

		self._sensor_states = {}
		self._dirty = False

	def __getitem__(self, key):
		return self._state.__getitem__(key)

	@property
	def ip(self):
		return self._ip
	@property
	def mac(self):
		return self._mac

	@property
	def state(self):
		return self._state

	@property
	def dirty(self):
		return self._dirty
	@dirty.setter
	def dirty(self, val):
		self._dirty = val

	def update(self):
		"""
		Update config.
		"""
		for sensor in self._state["deconz"]["sensors"].keys():
			if "modelid" not in self._state["deconz"]["sensors"][sensor]:
				self._state["deconz"]["sensors"]["modelid"] = self._state["sensors"][self._state["deconz"]["sensors"][sensor]["bridgeid"]]["modelid"]
			if self._state["deconz"]["sensors"][sensor]["modelid"] == "TRADFRI motion sensor":
				if "lightsensor" not in self._state["deconz"]["sensors"][sensor]:
					self._state["deconz"]["sensors"][sensor]["lightsensor"] = "internal"
		for sensor in self._state["sensors"].keys():
			if self._state["sensors"][sensor]["type"] == "CLIPGenericStatus":
				self._state["sensors"][sensor]["state"]["status"] = 0

	def save(self, filename=None):
		"""
		Save config to file.
		"""

		# TODO: spawn thread to do save,
		# 		catch sigterms and force save

		if not filename:
			filename = self.filename
		with open(filename, 'w') as fp:
			json.dump(self._state, fp, sort_keys=True, indent=4, separators=(',', ': '))

	def load(self, filename=None):
		"""
		Load config from file.
		"""
		if not filename:
			filename = self.filename
		try:
			with open(filename, 'r') as fp:
				self._state = json.load(fp)
				print("[BridgeConfig] Config loaded.")
		except Exception as e:
			print("[BridgeConfig] CRITICAL! Failed to load config: {}".format(e))
			sys.exit(1)

	def next_free_id(self, element):
		"""
		Get next free ID
		"""
		i = 1
		while (str(i)) in self._state[element]:
			i += 1
		return str(i)

	def generate_sensor_states(self):
		"""
		Generate sensor states
		"""
		for sensor in self._state["sensors"]:
			if sensor not in self._sensor_states and "state" in self._state["sensors"][sensor]:
				self._sensor_states[sensor] = {"state": {}}
				for key in self._state["sensors"][sensor]["state"].keys():
					if key in ["lastupdated", "presence", "flag", "dark", "daylight", "status"]:
						self._sensor_states[sensor]["state"].update({key: datetime.now()})


	def load_alarm_config(self):
		"""
		Load and configure alarm virtual light
		"""
		if self._state["alarm_config"]["mail_username"] != "":
			print("E-mail account configured")
			if "virtual_light" not in self._state["alarm_config"]:
				print("Send test email")
				if sendEmail("dummy test"):
					print("Mail succesfully sent\nCreate alarm virtual light")
					new_light_id = next_free_id("lights")
					self._state["lights"][new_light_id] = {"state": {"on": False, "bri": 200, "hue": 0, "sat": 0, "xy": [0.690456, 0.295907], "ct": 461, "alert": "none", "effect": "none", "colormode": "xy", "reachable": True}, "type": "Extended color light", "name": "Alarm", "uniqueid": "1234567ffffff", "modelid": "LLC012", "swversion": "66009461"}
					self._state["alarm_config"]["virtual_light"] = new_light_id
				else:
					print("Mail test failed")