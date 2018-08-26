"""
BridgeEmulator
08/19/18
"""

from .controllers import SSDPController
from .controllers import EntertainmentController
from .controllers import SchedulerController
from .controllers import HueController
from .controllers import DeconzController

_UPDATE_LIGHTS_ON_START = False

class BridgeEmulator(object):
	def __init__(self, bridge_config, ip=None, mac=None):
		"""
		Create BridgeEmulator instance.
		Creates controller threads for each controller type in controllers.

		:param bridge_config: BridgeConfig object
		"""
		self.bridge_config = bridge_config
		self.ip = ip
		self.mac = mac

		self._controllers = {}

    	try:
	        if _UPDATE_LIGHTS_ON_START:
	            self.update_all_lights()
	        if self.bridge_config["deconz"]["enabled"]:
		        self._controllers['SSDP'] = SSDPController(ip=ip,mac=mac)

		    self._controllers['scheduler'] = SchedulerController(ip=ip,mac=mac)
		    self._controllers['entertainment'] = EntertainmentController(ip=ip,mac=mac)

		    for key in self._controllers:
		    	self._controllers[key].start()

	        # Thread(target=ssdpSearch, args=[getIpAddress(), mac]).start()
	        # Thread(target=ssdpBroadcast, args=[getIpAddress(), mac]).start()
	        # Thread(target=schedulerProcessor).start()
	        # Thread(target=syncWithLights).start()
	        # Thread(target=entertainmentService).start()
	        # Thread(target=run, args=[False]).start()
	        # Thread(target=run, args=[True]).start()
	        # Thread(target=daylightSensor).start()
	        
	    except Exception as e:
	        print("[Emulator] Failed to initialize: {}".format(e))

	def join_all(self):
		"""
		Wait for threads to join
		"""
		for key in self._controllers:
			self._controllers[key].join()
		
	def update_all_lights(self, *args, **kwds):
		"""
		Update all lights to state found in config.
		Useful for power outages.
		"""

	    for light in self.bridge_config["lights_address"]:
	        payload = {}
	        payload["on"] = self.bridge_config["lights"][light]["state"]["on"]
	        if payload["on"] and "bri" in self.bridge_config["lights"][light]["state"]:
	            payload["bri"] = self.bridge_config["lights"][light]["state"]["bri"]

	        self.send_light_request(light, payload)
	        sleep(0.5)
	        print("Update status for light: {}".format(light))

	def send_light_request(self, light, data):
	    """
	    Send light request to 
	    """
	    payload = {}
	    if light in bridge_config["lights_address"]:
	    	""" If light has an address associated with it. """
	        if bridge_config["lights_address"][light]["protocol"] == "native":
	        	#ESP8266 light or strip
	        	self.
	            url = "http://" + bridge_config["lights_address"][light]["ip"] + "/set?light=" + str(bridge_config["lights_address"][light]["light_nr"]);
	            method = 'GET'
	            for key, value in data.items():
	                if key == "xy":
	                    url += "&x=" + str(value[0]) + "&y=" + str(value[1])
	                else:
	                    url += "&" + key + "=" + str(value)
	        elif bridge_config["lights_address"][light]["protocol"] in ["hue","deconz"]: #Original Hue light or Deconz light
	            url = "http://" + bridge_config["lights_address"][light]["ip"] + "/api/" + bridge_config["lights_address"][light]["username"] + "/lights/" + bridge_config["lights_address"][light]["light_id"] + "/state"
	            method = 'PUT'
	            payload.update(data)

	        elif bridge_config["lights_address"][light]["protocol"] == "domoticz": #Domoticz protocol
	            url = "http://" + bridge_config["lights_address"][light]["ip"] + "/json.htm?type=command&param=switchlight&idx=" + bridge_config["lights_address"][light]["light_id"];
	            method = 'GET'
	            for key, value in data.items():
	                if key == "on":
	                    if value:
	                        url += "&switchcmd=On"
	                    else:
	                        url += "&switchcmd=Off"
	                elif key == "bri":
	                    url += "&switchcmd=Set%20Level&level=" + str(round(float(value)/255*100)) # domoticz range from 0 to 100 (for zwave devices) instead of 0-255 of bridge

	        elif bridge_config["lights_address"][light]["protocol"] == "milight": #MiLight bulb
	            url = "http://" + bridge_config["lights_address"][light]["ip"] + "/gateways/" + bridge_config["lights_address"][light]["device_id"] + "/" + bridge_config["lights_address"][light]["mode"] + "/" + str(bridge_config["lights_address"][light]["group"]);
	            method = 'PUT'
	            for key, value in data.items():
	                if key == "on":
	                    payload["status"] = value
	                elif key == "bri":
	                    payload["brightness"] = value
	                elif key == "ct":
	                    payload["color_temp"] = int(value / 1.6 + 153)
	                elif key == "hue":
	                    payload["hue"] = value / 180
	                elif key == "sat":
	                    payload["saturation"] = value * 100 / 255
	                elif key == "xy":
	                    payload["color"] = {}
	                    (payload["color"]["r"], payload["color"]["g"], payload["color"]["b"]) = convert_xy(value[0], value[1], bridge_config["lights"][light]["state"]["bri"])
	            print(json.dumps(payload))
	        elif bridge_config["lights_address"][light]["protocol"] == "yeelight": #YeeLight bulb
	            url = "http://" + str(bridge_config["lights_address"][light]["ip"])
	            method = 'TCP'
	            transitiontime = 400
	            if "transitiontime" in data:
	                transitiontime = data["transitiontime"] * 100
	            for key, value in data.items():
	                if key == "on":
	                    if value:
	                        payload["set_power"] = ["on", "smooth", transitiontime]
	                    else:
	                        payload["set_power"] = ["off", "smooth", transitiontime]
	                elif key == "bri":
	                    payload["set_bright"] = [int(value / 2.55) + 1, "smooth", transitiontime]
	                elif key == "ct":
	                    payload["set_ct_abx"] = [int(1000000 / value), "smooth", transitiontime]
	                elif key == "hue":
	                    payload["set_hsv"] = [int(value / 182), int(bridge_config["lights"][light]["state"]["sat"] / 2.54), "smooth", transitiontime]
	                elif key == "sat":
	                    payload["set_hsv"] = [int(value / 2.54), int(bridge_config["lights"][light]["state"]["hue"] / 2.54), "smooth", transitiontime]
	                elif key == "xy":
	                    color = convert_xy(value[0], value[1], bridge_config["lights"][light]["state"]["bri"])
	                    payload["set_rgb"] = [(color[0] * 65536) + (color[1] * 256) + color[2], "smooth", transitiontime] #according to docs, yeelight needs this to set rgb. its r * 65536 + g * 256 + b
	                elif key == "alert" and value != "none":
	                    payload["start_cf"] = [ 4, 0, "1000, 2, 5500, 100, 1000, 2, 5500, 1, 1000, 2, 5500, 100, 1000, 2, 5500, 1"]


	        elif bridge_config["lights_address"][light]["protocol"] == "ikea_tradfri": #IKEA Tradfri bulb
	            url = "coaps://" + bridge_config["lights_address"][light]["ip"] + ":5684/15001/" + str(bridge_config["lights_address"][light]["device_id"])
	            for key, value in data.items():
	                if key == "on":
	                    payload["5850"] = int(value)
	                elif key == "transitiontime":
	                    payload["5712"] = value
	                elif key == "bri":
	                    payload["5851"] = value
	                elif key == "ct":
	                    if value < 270:
	                        payload["5706"] = "f5faf6"
	                    elif value < 385:
	                        payload["5706"] = "f1e0b5"
	                    else:
	                        payload["5706"] = "efd275"
	                elif key == "xy":
	                    payload["5709"] = int(value[0] * 65535)
	                    payload["5710"] = int(value[1] * 65535)
	            if "hue" in data or "sat" in data:
	                if("hue" in data):
	                    hue = data["hue"]
	                else:
	                    hue = bridge_config["lights"][light]["state"]["hue"]
	                if("sat" in data):
	                    sat = data["sat"]
	                else:
	                    sat = bridge_config["lights"][light]["state"]["sat"]
	                if("bri" in data):
	                    bri = data["bri"]
	                else:
	                    bri = bridge_config["lights"][light]["state"]["bri"]
	                rgbValue = hsv_to_rgb(hue, sat, bri)
	                xyValue = convert_rgb_xy(rgbValue[0], rgbValue[1], rgbValue[2])
	                payload["5709"] = int(xyValue[0] * 65535)
	                payload["5710"] = int(xyValue[1] * 65535)
	            if "5850" in payload and payload["5850"] == 0:
	                # Setting brightnes will turn on the light,
	                # even if there was a request to power off
	                payload.clear()
	                payload["5850"] = 0
	            elif "5850" in payload and "5851" in payload: 
	            	# When setting brightness,
	            	# don't send power on command
	                del payload["5850"]
	        elif bridge_config["lights_address"][light]["protocol"] == "flex":
	            msg = bytearray()
	            if "on" in data:
	                if data["on"]:
	                    msg = bytearray([0x71, 0x23, 0x8a, 0x0f])
	                else:
	                    msg = bytearray([0x71, 0x24, 0x8a, 0x0f])
	                checksum = sum(msg) & 0xFF
	                msg.append(checksum)
	                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
	                sock.sendto(msg, (bridge_config["lights_address"][light]["ip"], 48899))
	            if ("bri" in data and bridge_config["lights"][light]["state"]["colormode"] == "xy") or "xy" in data:
	                pprint(data)
	                bri = data["bri"] if "bri" in data else bridge_config["lights"][light]["state"]["bri"]
	                xy = data["xy"] if "xy" in data else bridge_config["lights"][light]["state"]["xy"]
	                rgb = convert_xy(xy[0], xy[1], bri)
	                msg = bytearray([0x41, rgb[0], rgb[1], rgb[2], 0x00, 0xf0, 0x0f])
	                checksum = sum(msg) & 0xFF
	                msg.append(checksum)
	                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
	                sock.sendto(msg, (bridge_config["lights_address"][light]["ip"], 48899))
	            elif ("bri" in data and bridge_config["lights"][light]["state"]["colormode"] == "ct") or "ct" in data:
	                bri = data["bri"] if "bri" in data else bridge_config["lights"][light]["state"]["bri"]
	                msg = bytearray([0x41, 0x00, 0x00, 0x00, bri, 0x0f, 0x0f])
	                checksum = sum(msg) & 0xFF
	                msg.append(checksum)
	                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
	                sock.sendto(msg, (bridge_config["lights_address"][light]["ip"], 48899))

	        try:
	            if bridge_config["lights_address"][light]["protocol"] == "ikea_tradfri":
	                if "5712" not in payload:
	                    payload["5712"] = 4 #If no transition add one, might also add check to prevent large transitiontimes
	                    check_output("./coap-client-linux -m put -u \"" + bridge_config["lights_address"][light]["identity"] + "\" -k \"" + bridge_config["lights_address"][light]["preshared_key"] + "\" -e '{ \"3311\": [" + json.dumps(payload) + "] }' \"" + url + "\"", shell=True)
	            elif bridge_config["lights_address"][light]["protocol"] in ["hue", "deconz"]:
	                color = {}
	                if "xy" in payload:
	                    color["xy"] = payload["xy"]
	                    del(payload["xy"])
	                elif "ct" in payload:
	                    color["ct"] = payload["ct"]
	                    del(payload["ct"])
	                elif "hue" in payload:
	                    color["hue"] = payload["hue"]
	                    del(payload["hue"])
	                elif "sat" in payload:
	                    color["sat"] = payload["sat"]
	                    del(payload["sat"])
	                if len(payload) != 0:
	                    sendRequest(url, method, json.dumps(payload))
	                    sleep(1)
	                if len(color) != 0:
	                    sendRequest(url, method, json.dumps(color))
	            else:
	                sendRequest(url, method, json.dumps(payload))
	        except:
	            bridge_config["lights"][light]["state"]["reachable"] = False
	            print("request error")
	        else:
	            bridge_config["lights"][light]["state"]["reachable"] = True
	            print("LightRequest: " + url)