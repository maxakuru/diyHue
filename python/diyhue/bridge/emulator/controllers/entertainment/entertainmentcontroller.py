"""
EntertainmentController

"""

from time import sleep
import socket
from diyhue.bridge.utils import convert_xy, convert_rgb_xy
from ..controller import ControllerProcess

_LOCALHOST = '127.0.0.1'
_ENTERTAINMENT_PORT = 2101

# consts
_BRIGHTNESS_THRESHOLD = 50
_FRAME_RATE = 24 # FPS

# packet consts See README for packet definition
_PROTOCOL = 'HueStream'
_RGB_CODE = 0
_CIE_CODE = 1
_HEADER_SIZE = 16
_LIGHT_CODE = 0

class EntertainmentController(ControllerProcess):
	def __init__(self, emulator, ip, mac):
		super().__init__()
		self._emulator = emulator
		self._ip = ip
		self._mac = mac
		self._socket = None
		self._bridge_config = self._emulator.bridge_config
		self._light_status = {}

		self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self._socket.bind((_LOCALHOST, _ENTERTAINMENT_PORT))

	@property
	def light_status(self):
		return self._light_status
	@light_status.setter
	def light_status(self, val):
		self._light_status = val
	@property
	def bridge_config(self):
		return self._bridge_config
	@property
	def emulator(self):
		return self._emulator
	@property
	def ip(self):
		return self._ip
	@property
	def mac(self):
		return self._mac
	@property
	def socket(self):
		return self._socket

	def run(self):
		"""
		Main thread loop.
		
		Read chunk of data from socket
		If protocol matches current protocol,
		handle packet with corresponding color space handler.
		"""
		self.alive = True
		count = 0
		self.light_status = {}
		while self.alive:
			# Read 106 bytes from socket
			data = self.socket.recvfrom(106)[0]
			native_lights = {}
			if data[:9].decode('utf-8') != _PROTOCOL: 
				continue

			if data[14] == _RGB_CODE: 
				self.handle_rgb(data, _HEADER_SIZE, native_lights)
			elif data[14] == _CIE_CODE:
				self.handle_cie(data, _HEADER_SIZE, native_lights)

			if len(native_lights) > 0:
				self.send_native_requests(native_lights)

	def handle_rgb(self, data, i, native_lights):
		"""
		Handle RGB color space update.

		:param data: bytes, packet data to process
		:param i: int, number of bytes in header
		:param native_lights: dict, lights with native protocol
		"""
		while i < len(data):
			if data[i] == _LIGHT_CODE:
				light_id = data[i+1] * 256 + data[i+2]
				if light_id != 0:
					r = int((data[i+3] * 256 + data[i+4]) / 256)
					g = int((data[i+5] * 256 + data[i+6]) / 256)
					b = int((data[i+7] * 256 + data[i+7]) / 256)
					if light_id not in self.light_status:
						self.light_status[light_id] = {"on": False, "bri": 1}
					if r == 0 and  g == 0 and  b == 0:
						self.bridge_config["lights"][str(light_id)]["state"]["on"] = False
					else:
						self.bridge_config["lights"][str(light_id)]["state"].update({"on": True, 
							                                           "bri": int((r + g + b) / 3), 
							                                           "xy": convert_rgb_xy(r, g, b), 
							                                           "colormode": "xy"})
					
					if self.bridge_config["lights_address"][str(light_id)]["protocol"] == "native":
						nlight_ip = self.bridge_config["lights_address"][str(light_id)]["ip"]
						if nlight_ip not in native_lights:
							native_lights[nlight_ip] = {}
						
						nlight_nr = (self.bridge_config["lights_address"][str(light_id)]["light_nr"]-1)
						native_lights[nlight_ip][nlight_nr] = [r, g, b]
					else:
						if count%_FRAME_RATE==0: # => every seconds, increase in case the destination device is overloaded
							if r == 0 and  g == 0 and  b == 0:
								# turn light off, if on
								if light_status[light_id]["on"]:
									self.emulator.send_light_request(str(light_id), {
																		"on": False, 
																		"transitiontime": 3})
									light_status[light_id]["on"] = False

							elif light_status[light_id]["on"] == False:
								self.emulator.send_light_request(str(light_id), {
																	"on": True, 
																	"transitiontime": 3})
								light_status[light_id]["on"] = True
							elif abs(int((r + b + g) / 3) - light_status[light_id]["bri"]) > _BRIGHTNESS_THRESHOLD:
								# send brightness only of difference is bigger than this value
								self.emulator.send_light_request(str(light_id), {
																	"bri": int((r + b + g) / 3), 
																	"transitiontime": 3})
								light_status[light_id]["bri"] = int((r + b + g) / 3)
							else:
								self.emulator.send_light_request(str(light_id), {
																	"xy": convert_rgb_xy(r, g, b), 
																	"transitiontime": 3})
					count += 1
					if count >= __FRAME_RATE:
						count = 0
					updateGroupStats(light_id)
				i += 9

	def handle_cie(self, data, i, native_lights):
		"""
		Handle CIE colorspace updates.
		:param data: bytes, data to process
		:param i: int, number of bytes in header
		:param native_lights: lights with native protocol
		"""
		while i < len(data):
			if data[i] == _LIGHT_CODE:
				light_id = data[i+1] * 256 + data[i+2]
				if light_id != 0:
					x = (data[i+3] * 256 + data[i+4]) / 65535
					y = (data[i+5] * 256 + data[i+6]) / 65535
					bri = int((data[i+7] * 256 + data[i+7]) / 256)
					if bri == 0:
						self.bridge_config["lights"][str(light_id)]["state"]["on"] = False
					else:
						self.bridge_config["lights"][str(light_id)]["state"].update({"on": True, 
																				"bri": bri, 
																				"xy": [x,y], 
																				"colormode": "xy"})
					if self.bridge_config["lights_address"][str(light_id)]["protocol"] == "native":
						nlight_ip = self.bridge_config["lights_address"][str(light_id)]["ip"]
						if nlight_ip not in nativeLights:
							nativeLights[nlight_ip] = {}
						nlight_nr = (self.bridge_config["lights_address"][str(light_id)]["light_nr"]-1)
						nativeLights[nlight_ip][nlight_nr] = convert_xy(x, y, bri)
					else:
						count += 1
						if count%_FRAME_RATE==0:
							# throttle requests to avoid overloading receiver
							self.emulator.send_light_request(str(light_id), {"xy": [x,y]})
							count = 0
					updateGroupStats(light_id)
				i+=9

	def send_native_requests(self, native_lights):
		"""
		Send light update requests to lights with protocol "native".

		:param nativeLights: dict
		:return: None
		"""
		if len(native_lights)<1: return
		for ip in native_lights.keys():
			# build UDP message
			udpmsg = bytearray()
			for light in native_lights[ip].keys():
				udpmsg += (bytes([light]) + 
							bytes([native_lights[ip][light][0]]) + 
							bytes([native_lights[ip][light][1]]) + 
							bytes([native_lights[ip][light][2]]))
			# send message
			self.emulator.send_dgram(message=udpmsg, ip=ip, port=2100)

	def close(self):
		"""
		Set thread to close.
		"""
		self.alive = False