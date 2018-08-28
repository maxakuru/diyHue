import random
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from .pages import *

class S(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'nginx'
    sys_version = ''

    def __init__(self, ip, mac, callbacks={}):
        """
        Init server and set callbacks, passed in from Emulator.

        Callback keys:
        "save_config" ->()-> save bridge config
        "register_mi_light" ->()-> register mi light, return mi light
        "register_identity" ->(get_params)
        "scan_tradfri" ->()-> scan for tradfri devices, return list of devices
        "whitelist_user" ->()-> create a whitelist user is none exist, return ApiKey
        """
        self.callbacks = callbacks
        self.ip = ip
        self.mac = mac

        self._mimetypes = {"json": "application/json", 
                        "map": "application/json", 
                        "html": "text/html", 
                        "xml": "application/xml", 
                        "js": "text/javascript", 
                        "css": "text/css", 
                        "png": "image/png"}

    def _set_headers(self):
        self.send_response(200)
        if self.path.endswith((".html",".json",".css",".map",".png",".js", ".xml")):
            self.send_header('Content-type', self._mimetypes[self.path.split(".")[-1]])
        elif self.path.startswith("/api"):
            self.send_header('Content-type', self._mimetypes["json"])
        else:
            self.send_header('Content-type', self._mimetypes["html"])

    def _set_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Hue\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def _set_end_headers(self, data):
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        """
        Handle GET request.
        """
        # / or /index
        if self.path == '/' or self.path == '/index.html':
            self._set_headers()
            f = open('./web-ui/index.html')
            self._set_end_headers(bytes(f.read(), "utf8"))
        # /debug/clip.html
        elif self.path == "/debug/clip.html":
            self._set_headers()
            f = open('./clip.html', 'rb')
            self._set_end_headers(f.read())
        # /config.js
        elif self.path == '/config.js':
            self._set_headers()
            # Whitelist user
            api_key = self.callbacks['whitelist_user']()
            self._set_end_headers(
                bytes('window.config = { API_KEY: "{}",};'.format(api_key), 
                        "utf8"))
        # /___.css/map/png/js
        elif self.path.endswith((".css",".map",".png",".js")):
            self._set_headers()
            f = open('./web-ui' + self.path, 'rb')
            self._set_end_headers(f.read())
        # /description.xml
        elif self.path == '/description.xml':
            self._set_headers()
            self._set_end_headers(bytes(description(self.ip, self.mac), "utf8"))
        # /save
        elif self.path == '/save':
            self._set_headers()
            # callback
            self.callbacks['save_config']()
            self._set_end_headers(bytes(json.dumps(
                [{"success":{
                    "configuration":"saved",
                    "filename":"/opt/hue-emulator/config.json"
                    }}],separators=(',', ':')), "utf8"))
        # /tradfri setup Tradfri gateway
        elif self.path.startswith("/tradfri"):
            self._set_headers()
            get_parameters = parse_qs(urlparse(self.path).query)
            if "code" in get_parameters:
                # Register new Tradfri identity
                # callback
                self.callbacks['register_tradfri_identity'](get_parameters)

                # callback
                lights_found = self.['scan_tradfri']()
                self._set_end_headers(
                    bytes(tradfriTemplate(lightsfound), "utf8"))
            else:
                self._set_end_headers(
                    bytes(tradfriTemplate(), "utf8"))
        # /milight setup milight bulb
        elif self.path.startswith("/milight"):
            self._set_headers()
            get_params = parse_qs(urlparse(self.path).query)
            if "device_id" in get_parameters:
                # Register new mi light
                # callback
                milight = self.callbacks['register_mi_light'](get_params)
                self._set_end_headers(bytes(
                        milightTemplate("<br> Light added"), "utf8"))
            else:
                self._set_end_headers(bytes(
                        milightTemplate(), "utf8"))

        # /hue -> setup Hue bridge
        elif self.path.startswith("/hue"):
            # Hub Sync button emulated
            if "linkbutton" in self.path:
                if self.headers['Authorization']==None:
                    self._set_AUTHHEAD()
                    self._set_end_headers(bytes(
                            'You are not authenticated', "utf8"))
                    return
                # callback
                auth = self.callbacks['check_auth'](self.headers['Authorization'])
                if auth:
                    get_parameters = parse_qs(urlparse(self.path).query)
                    if "action=Activate" in self.path:
                        self._set_headers()
                        self.callbacks["activate_link_button"]()
                        self._set_end_headers(bytes(
                            hueTemplate("You have 30 sec to connect your device"), "utf8"))
                    elif "action=Exit" in self.path:
                        self._set_AUTHHEAD()
                        self._set_end_headers(bytes(
                                'You are succesfully disconnected', "utf8"))
                    elif "action=ChangePassword" in self.path:
                        self._set_headers()
                        # callback
                        success = self.callbacks['change_hue_password']()
                        if success:
                            self._set_end_headers(bytes(
                                hueTemplate('Password changed.'+
                                    ' Please logout then login again.'), 'utf8'))
                        else:
                            self._set_end_headers(bytes(
                                hueTemplate('Failed to change password.'+
                                    ' Please try again.'), 'utf8'))
                    else:
                        self._set_headers()
                        self._set_end_headers(bytes(hueTemplate(), "utf8"))
                    pass
                else:
                    self._set_AUTHHEAD()
                    self._set_end_headers(bytes(self.headers.headers['Authorization'], "utf8"))
                    self._set_end_headers(bytes('Not authenticated', "utf8"))
                    pass
            else:
                self._set_headers()
                get_parameters = parse_qs(urlparse(self.path).query)
                if "ip" in get_parameters:
                    response = json.loads(sendRequest("http://" + get_parameters["ip"][0] + "/api/", "POST", "{\"devicetype\":\"Hue Emulator\"}"))
                    if "success" in response[0]:
                        hue_lights = json.loads(sendRequest("http://" + get_parameters["ip"][0] + "/api/" + response[0]["success"]["username"] + "/lights", "GET", "{}"))
                        lights_found = 0
                        for hue_light in hue_lights:
                            new_light_id = nextFreeId("lights")
                            bridge_config["lights"][new_light_id] = hue_lights[hue_light]
                            bridge_config["lights_address"][new_light_id] = {"username": response[0]["success"]["username"], "light_id": hue_light, "ip": get_parameters["ip"][0], "protocol": "hue"}
                            lights_found += 1
                        if lights_found == 0:
                            self._set_end_headers(bytes(webform_hue() + "<br> No lights where found", "utf8"))
                        else:
                            self._set_end_headers(bytes(webform_hue() + "<br> " + str(lights_found) + " lights where found", "utf8"))
                    else:
                        self._set_end_headers(bytes(webform_hue() + "<br> unable to connect to hue bridge", "utf8"))
                else:
                    self._set_end_headers(bytes(webform_hue(), "utf8"))
        elif self.path.startswith("/deconz"): #setup imported deconz sensors
            self._set_headers()
            get_parameters = parse_qs(urlparse(self.path).query)
            #clean all rules related to deconz Switches
            if get_parameters:
                emulator_resourcelinkes = []
                for resourcelink in bridge_config["resourcelinks"].keys(): # delete all previews rules of IKEA remotes
                    if bridge_config["resourcelinks"][resourcelink]["classid"] == 15555:
                        emulator_resourcelinkes.append(resourcelink)
                        for link in bridge_config["resourcelinks"][resourcelink]["links"]:
                            pices = link.split('/')
                            if pices[1] == "rules":
                                try:
                                    del bridge_config["rules"][pices[2]]
                                except:
                                    print("unable to delete the rule " + pices[2])
                for resourcelink in emulator_resourcelinkes:
                    del bridge_config["resourcelinks"][resourcelink]
                for key in get_parameters.keys():
                    if get_parameters[key][0] in ["ZLLSwitch", "ZGPSwitch"]:
                        try:
                            del bridge_config["sensors"][key]
                        except:
                            pass
                        hueSwitchId = addHueSwitch("", get_parameters[key][0])
                        for sensor in bridge_config["deconz"]["sensors"].keys():
                            if bridge_config["deconz"]["sensors"][sensor]["bridgeid"] == key:
                                bridge_config["deconz"]["sensors"][sensor] = {"hueType": get_parameters[key][0], "bridgeid": hueSwitchId}
                    else:
                        if not key.startswith("mode_"):
                            if bridge_config["sensors"][key]["modelid"] == "TRADFRI remote control":
                                if get_parameters["mode_" + key][0]  == "CT":
                                    addTradfriCtRemote(key, get_parameters[key][0])
                                elif get_parameters["mode_" + key][0]  == "SCENE":
                                    addTradfriSceneRemote(key, get_parameters[key][0])
                            elif bridge_config["sensors"][key]["modelid"] == "TRADFRI wireless dimmer":
                                addTradfriDimmer(key, get_parameters[key][0])
                            elif bridge_config["deconz"]["sensors"][key]["modelid"] == "TRADFRI motion sensor":
                                bridge_config["deconz"]["sensors"][key]["lightsensor"] = get_parameters[key][0]
                            #store room id in deconz sensors
                            for sensor in bridge_config["deconz"]["sensors"].keys():
                                if bridge_config["deconz"]["sensors"][sensor]["bridgeid"] == key:
                                    bridge_config["deconz"]["sensors"][sensor]["room"] = get_parameters[key][0]
                                    if bridge_config["sensors"][key]["modelid"] == "TRADFRI remote control":
                                        bridge_config["deconz"]["sensors"][sensor]["opmode"] = get_parameters["mode_" + key][0]

            else:
                scanDeconz()
            self._set_end_headers(bytes(webformDeconz({"deconz": bridge_config["deconz"], "sensors": bridge_config["sensors"], "groups": bridge_config["groups"]}), "utf8"))
        elif self.path.startswith("/switch"): #request from an ESP8266 switch or sensor
            self._set_headers()
            get_parameters = parse_qs(urlparse(self.path).query)
            pprint(get_parameters)
            if "devicetype" in get_parameters: #register device request
                sensor_is_new = True
                for sensor in bridge_config["sensors"]:
                    if "uniqueid" in bridge_config["sensors"][sensor] and bridge_config["sensors"][sensor]["uniqueid"].startswith(get_parameters["mac"][0]): # if sensor is already present
                        sensor_is_new = False
                if sensor_is_new:
                    print("registering new sensor " + get_parameters["devicetype"][0])
                    new_sensor_id = nextFreeId("sensors")
                    if get_parameters["devicetype"][0] in ["ZLLSwitch","ZGPSwitch"]:
                        print(get_parameters["devicetype"][0])
                        addHueSwitch(get_parameters["mac"][0], get_parameters["devicetype"][0])
                    elif get_parameters["devicetype"][0] == "ZLLPresence":
                        print("ZLLPresence")
                        addHueMotionSensor(get_parameters["mac"][0])
                    generateSensorsState()
            else: #switch action request
                for sensor in bridge_config["sensors"]:
                    if "uniqueid" in bridge_config["sensors"][sensor] and bridge_config["sensors"][sensor]["uniqueid"].startswith(get_parameters["mac"][0]) and bridge_config["sensors"][sensor]["config"]["on"]: #match senser id based on mac address
                        print("match sensor " + str(sensor))
                        current_time = datetime.now()
                        if bridge_config["sensors"][sensor]["type"] == "ZLLSwitch" or bridge_config["sensors"][sensor]["type"] == "ZGPSwitch":
                            bridge_config["sensors"][sensor]["state"].update({"buttonevent": get_parameters["button"][0], "lastupdated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")})
                            sensors_state[sensor]["state"]["lastupdated"] = current_time
                        elif bridge_config["sensors"][sensor]["type"] == "ZLLPresence":
                            if bridge_config["sensors"][sensor]["state"]["presence"] != True:
                                bridge_config["sensors"][sensor]["state"]["presence"] = True
                                sensors_state[sensor]["state"]["presence"] = current_time
                                Thread(target=motionDetected, args=[sensor]).start()
                            bridge_config["sensors"][sensor]["state"]["lastupdated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

                        elif bridge_config["sensors"][sensor]["type"] == "ZLLLightLevel":
                            if bridge_config["sensors"]["1"]["modelid"] == "PHDL00" and bridge_config["sensors"]["1"]["state"]["daylight"]:
                                bridge_config["sensors"][sensor]["state"]["lightlevel"] = 25000
                                bridge_config["sensors"][sensor]["state"]["dark"] = False
                            else:
                                bridge_config["sensors"][sensor]["state"]["lightlevel"] = 6000
                                bridge_config["sensors"][sensor]["state"]["dark"] = True

                            #if alarm is activ trigger the alarm
                            if "virtual_light" in bridge_config["alarm_config"] and bridge_config["lights"][bridge_config["alarm_config"]["virtual_light"]]["state"]["on"] and bridge_config["sensors"][sensor]["state"]["presence"] == True:
                                sendEmail(bridge_config["sensors"][sensor]["name"])
                                #triger_horn() need development
                        rulesProcessor(sensor, current_time) #process the rules to perform the action configured by application
            self._set_end_headers(bytes("done", "utf8"))
        else:
            url_pices = self.path.split('/')
            if len(url_pices) < 3:
                #self._set_headers_error()
                self.send_error(404, 'not found')
                return
            else:
                self._set_headers()
            if url_pices[2] in bridge_config["config"]["whitelist"]: #if username is in whitelist
                bridge_config["config"]["UTC"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                bridge_config["config"]["localtime"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                bridge_config["config"]["whitelist"][url_pices[2]]["last use date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                if len(url_pices) == 3 or (len(url_pices) == 4 and url_pices[3] == ""): #print entire config
                    self._set_end_headers(bytes(json.dumps({"lights": bridge_config["lights"], "groups": bridge_config["groups"], "config": bridge_config["config"], "scenes": bridge_config["scenes"], "schedules": bridge_config["schedules"], "rules": bridge_config["rules"], "sensors": bridge_config["sensors"], "resourcelinks": bridge_config["resourcelinks"]},separators=(',', ':')), "utf8"))
                elif len(url_pices) == 4 or (len(url_pices) == 5 and url_pices[4] == ""): #print specified object config
                    self._set_end_headers(bytes(json.dumps(bridge_config[url_pices[3]],separators=(',', ':')), "utf8"))
                elif len(url_pices) == 5 or (len(url_pices) == 6 and url_pices[5] == ""):
                    if url_pices[4] == "new": #return new lights and sensors only
                        new_lights.update({"lastscan": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")})
                        self._set_end_headers(bytes(json.dumps(new_lights ,separators=(',', ':')), "utf8"))
                        new_lights.clear()
                    elif url_pices[3] == "groups" and url_pices[4] == "0":
                        any_on = False
                        all_on = True
                        for group_state in bridge_config["groups"].keys():
                            if bridge_config["groups"][group_state]["state"]["any_on"] == True:
                                any_on = True
                            else:
                                all_on = False
                        self._set_end_headers(bytes(json.dumps({"name":"Group 0","lights": [l for l in bridge_config["lights"]],"type":"LightGroup","state":{"all_on":all_on,"any_on":any_on},"recycle":False,"action":{"on":True,"bri":254,"hue":47258,"sat":253,"effect":"none","xy":[0.1424,0.0824],"ct":153,"alert":"none","colormode":"xy"}},separators=(',', ':')), "utf8"))
                    elif url_pices[3] == "info":
                        self._set_end_headers(bytes(json.dumps(bridge_config["capabilities"][url_pices[4]],separators=(',', ':')), "utf8"))
                    else:
                        self._set_end_headers(bytes(json.dumps(bridge_config[url_pices[3]][url_pices[4]],separators=(',', ':')), "utf8"))
            elif (url_pices[2] == "nouser" or url_pices[2] == "none" or url_pices[2] == "config"): #used by applications to discover the bridge
                self._set_end_headers(bytes(json.dumps({"name": bridge_config["config"]["name"],"datastoreversion": 70, "swversion": bridge_config["config"]["swversion"], "apiversion": bridge_config["config"]["apiversion"], "mac": bridge_config["config"]["mac"], "bridgeid": bridge_config["config"]["bridgeid"], "factorynew": False, "replacesbridgeid": None, "modelid": bridge_config["config"]["modelid"],"starterkitid":""},separators=(',', ':')), "utf8"))
            else: #user is not in whitelist
                self._set_end_headers(bytes(json.dumps([{"error": {"type": 1, "address": self.path, "description": "unauthorized user" }}],separators=(',', ':')), "utf8"))


    def do_POST(self):
        self._set_headers()
        print ("in post method")
        print(self.path)
        self.data_string = b"{}" if self.headers['Content-Length'] is None else self.rfile.read(int(self.headers['Content-Length']))
        if self.path == "/updater":
            print("check for updates")
            update_data = json.loads(sendRequest("http://raw.githubusercontent.com/mariusmotea/diyHue/master/BridgeEmulator/updater", "GET", "{}"))
            for category in update_data.keys():
                for key in update_data[category].keys():
                    print("patch " + category + " -> " + key )
                    bridge_config[category][key] = update_data[category][key]
            self._set_end_headers(bytes(json.dumps([{"success": {"/config/swupdate/checkforupdate": True}}],separators=(',', ':')), "utf8"))
        else:
            raw_json = self.data_string.decode('utf8')
            raw_json = raw_json.replace("\t","")
            raw_json = raw_json.replace("\n","")
            post_dictionary = json.loads(raw_json)
            print(self.data_string)
        url_pices = self.path.split('/')
        if len(url_pices) == 4: #data was posted to a location
            if url_pices[2] in bridge_config["config"]["whitelist"]:
                if ((url_pices[3] == "lights" or url_pices[3] == "sensors") and not bool(post_dictionary)):
                    #if was a request to scan for lights of sensors
                    Thread(target=scanForLights).start()
                    sleep(7) #give no more than 5 seconds for light scanning (otherwise will face app disconnection timeout)
                    self._set_end_headers(bytes(json.dumps([{"success": {"/" + url_pices[3]: "Searching for new devices"}}],separators=(',', ':')), "utf8"))
                elif url_pices[3] == "":
                    self._set_end_headers(bytes(json.dumps([{"success": {"clientkey": "321c0c2ebfa7361e55491095b2f5f9db"}}],separators=(',', ':')), "utf8"))
                else: #create object
                    # find the first unused id for new object
                    new_object_id = nextFreeId(url_pices[3])
                    if url_pices[3] == "scenes":
                        post_dictionary.update({"lightstates": {}, "version": 2, "picture": "", "lastupdated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "owner" :url_pices[2]})
                        if "locked" not in post_dictionary:
                            post_dictionary["locked"] = False
                    elif url_pices[3] == "groups":
                        post_dictionary.update({"action": {"on": False}, "state": {"any_on": False, "all_on": False}})
                    elif url_pices[3] == "schedules":
                        post_dictionary.update({"created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "time": post_dictionary["localtime"]})
                        if post_dictionary["localtime"].startswith("PT"):
                            post_dictionary.update({"starttime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")})
                        if not "status" in post_dictionary:
                            post_dictionary.update({"status": "enabled"})
                    elif url_pices[3] == "rules":
                        post_dictionary.update({"owner": url_pices[2], "lasttriggered" : "none", "creationtime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "timestriggered": 0})
                        if not "status" in post_dictionary:
                            post_dictionary.update({"status": "enabled"})
                    elif url_pices[3] == "sensors":
                        if "state" not in post_dictionary:
                            post_dictionary["state"] = {}
                        if post_dictionary["modelid"] == "PHWA01":
                            post_dictionary.update({"state": {"status": 0}})
                    elif url_pices[3] == "resourcelinks":
                        post_dictionary.update({"owner" :url_pices[2]})
                    generateSensorsState()
                    bridge_config[url_pices[3]][new_object_id] = post_dictionary
                    print(json.dumps([{"success": {"id": new_object_id}}], sort_keys=True, indent=4, separators=(',', ': ')))
                    self._set_end_headers(bytes(json.dumps([{"success": {"id": new_object_id}}], separators=(',', ':')), "utf8"))
            else:
                self._set_end_headers(bytes(json.dumps([{"error": {"type": 1, "address": self.path, "description": "unauthorized user" }}], separators=(',', ':')), "utf8"))
                print(json.dumps([{"error": {"type": 1, "address": self.path, "description": "unauthorized user" }}],sort_keys=True, indent=4, separators=(',', ': ')))
        elif self.path.startswith("/api") and "devicetype" in post_dictionary: #new registration by linkbutton
            if int(bridge_config["linkbutton"]["lastlinkbuttonpushed"])+30 >= int(datetime.now().strftime("%s")) or bridge_config["config"]["linkbutton"]:
                username = hashlib.new('ripemd160', post_dictionary["devicetype"][0].encode('utf-8')).hexdigest()[:32]
                bridge_config["config"]["whitelist"][username] = {"last use date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),"create date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),"name": post_dictionary["devicetype"]}
                response = [{"success": {"username": username}}]
                if "generateclientkey" in post_dictionary and post_dictionary["generateclientkey"]:
                    response[0]["success"]["clientkey"] = "321c0c2ebfa7361e55491095b2f5f9db"
                self._set_end_headers(bytes(json.dumps(response,separators=(',', ':')), "utf8"))
                print(json.dumps(response, sort_keys=True, indent=4, separators=(',', ': ')))
            else:
                self._set_end_headers(bytes(json.dumps([{"error": {"type": 101, "address": self.path, "description": "link button not pressed" }}], separators=(',', ':')), "utf8"))
        saveConfig()

    def do_PUT(self):
        self._set_headers()
        print ("in PUT method")
        self.data_string = self.rfile.read(int(self.headers['Content-Length']))
        put_dictionary = json.loads(self.data_string.decode('utf8'))
        url_pices = self.path.split('/')
        print(self.path)
        print(self.data_string)
        if url_pices[2] in bridge_config["config"]["whitelist"]:
            if len(url_pices) == 4:
                bridge_config[url_pices[3]].update(put_dictionary)
                response_location = "/" + url_pices[3] + "/"
            if len(url_pices) == 5:
                if url_pices[3] == "schedules":
                    if "status" in put_dictionary and put_dictionary["status"] == "enabled" and bridge_config["schedules"][url_pices[4]]["localtime"].startswith("PT"):
                        put_dictionary.update({"starttime": (datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%S")})
                elif url_pices[3] == "scenes":
                    if "storelightstate" in put_dictionary:
                        for light in bridge_config["scenes"][url_pices[4]]["lightstates"]:
                            bridge_config["scenes"][url_pices[4]]["lightstates"][light] = {}
                            bridge_config["scenes"][url_pices[4]]["lightstates"][light]["on"] = bridge_config["lights"][light]["state"]["on"]
                            bridge_config["scenes"][url_pices[4]]["lightstates"][light]["bri"] = bridge_config["lights"][light]["state"]["bri"]
                            if "colormode" in bridge_config["lights"][light]["state"]:
                                if bridge_config["lights"][light]["state"]["colormode"] in ["ct", "xy"]:
                                    bridge_config["scenes"][url_pices[4]]["lightstates"][light][bridge_config["lights"][light]["state"]["colormode"]] = bridge_config["lights"][light]["state"][bridge_config["lights"][light]["state"]["colormode"]]
                                elif bridge_config["lights"][light]["state"]["colormode"] == "hs" and "hue" in bridge_config["scenes"][url_pices[4]]["lightstates"][light]:
                                    bridge_config["scenes"][url_pices[4]]["lightstates"][light]["hue"] = bridge_config["lights"][light]["state"]["hue"]
                                    bridge_config["scenes"][url_pices[4]]["lightstates"][light]["sat"] = bridge_config["lights"][light]["state"]["sat"]
                if url_pices[3] == "sensors":
                    current_time = datetime.now()
                    for key, value in put_dictionary.items():
                        if key not in sensors_state[url_pices[4]]:
                            sensors_state[url_pices[4]][key] = {}
                        if type(value) is dict:
                            bridge_config["sensors"][url_pices[4]][key].update(value)
                            for element in value.keys():
                                sensors_state[url_pices[4]][key][element] = current_time
                        else:
                            bridge_config["sensors"][url_pices[4]][key] = value
                            sensors_state[url_pices[3]][url_pices[4]][key] = current_time
                    rulesProcessor(url_pices[4], current_time)
                    if url_pices[4] == "1" and bridge_config[url_pices[3]][url_pices[4]]["modelid"] == "PHDL00":
                        bridge_config["sensors"]["1"]["config"]["configured"] = True ##mark daylight sensor as configured
                elif url_pices[3] == "groups" and "stream" in put_dictionary:
                    if "active" in put_dictionary["stream"]:
                        if put_dictionary["stream"]["active"]:
                            print("start hue entertainment")
                            Popen(["/opt/hue-emulator/entertainment-srv", "server_port=2100", "dtls=1", "psk_list=" + url_pices[2] + ",321c0c2ebfa7361e55491095b2f5f9db"])
                            sleep(0.2)
                            bridge_config["groups"][url_pices[4]]["stream"].update({"active": True, "owner": url_pices[2], "proxymode": "auto", "proxynode": "/bridge"})
                        else:
                            Popen(["killall", "entertainment-srv"])
                            bridge_config["groups"][url_pices[4]]["stream"].update({"active": False, "owner": None})
                    else:
                        bridge_config[url_pices[3]][url_pices[4]].update(put_dictionary)
                else:
                    bridge_config[url_pices[3]][url_pices[4]].update(put_dictionary)
                response_location = "/" + url_pices[3] + "/" + url_pices[4] + "/"
            if len(url_pices) == 6:
                if url_pices[3] == "groups": #state is applied to a group
                    if url_pices[5] == "stream":
                        if "active" in put_dictionary:
                            if put_dictionary["active"]:
                                print("start hue entertainment")
                                Popen(["/opt/hue-emulator/entertainment-srv", "server_port=2100", "dtls=1", "psk_list=" + url_pices[2] + ",321c0c2ebfa7361e55491095b2f5f9db"])
                                sleep(0.2)
                                bridge_config["groups"][url_pices[4]]["stream"].update({"active": True, "owner": url_pices[2], "proxymode": "auto", "proxynode": "/bridge"})
                            else:
                                Popen(["killall", "entertainment-srv"])
                                bridge_config["groups"][url_pices[4]]["stream"].update({"active": False, "owner": None})
                    elif "scene" in put_dictionary: #scene applied to group
                        #send all unique ip's in thread mode for speed
                        lightsIps = []
                        processedLights = []
                        for light in bridge_config["scenes"][put_dictionary["scene"]]["lights"]:
                            bridge_config["lights"][light]["state"].update(bridge_config["scenes"][put_dictionary["scene"]]["lightstates"][light])
                            if "xy" in bridge_config["scenes"][put_dictionary["scene"]]["lightstates"][light]:
                                bridge_config["lights"][light]["state"]["colormode"] = "xy"
                            elif "ct" in bridge_config["scenes"][put_dictionary["scene"]]["lightstates"][light]:
                                bridge_config["lights"][light]["state"]["colormode"] = "ct"
                            elif "hue" in bridge_config["scenes"][put_dictionary["scene"]]["lightstates"][light]:
                                bridge_config["lights"][light]["state"]["colormode"] = "hs"
                            if bridge_config["lights_address"][light]["ip"] not in lightsIps:
                                lightsIps.append(bridge_config["lights_address"][light]["ip"])
                                processedLights.append(light)
                                Thread(target=sendLightRequest, args=[light, bridge_config["scenes"][put_dictionary["scene"]]["lightstates"][light]]).start()
                        #now send the rest of the requests in non threaded mode
                        for light in bridge_config["scenes"][put_dictionary["scene"]]["lights"]:
                            if light not in processedLights:
                                sendLightRequest(light, bridge_config["scenes"][put_dictionary["scene"]]["lightstates"][light])
                            updateGroupStats(light)

                    elif "bri_inc" in put_dictionary:
                        bridge_config["groups"][url_pices[4]]["action"]["bri"] += int(put_dictionary["bri_inc"])
                        if bridge_config["groups"][url_pices[4]]["action"]["bri"] > 254:
                            bridge_config["groups"][url_pices[4]]["action"]["bri"] = 254
                        elif bridge_config["groups"][url_pices[4]]["action"]["bri"] < 1:
                            bridge_config["groups"][url_pices[4]]["action"]["bri"] = 1
                        bridge_config["groups"][url_pices[4]]["state"]["bri"] = bridge_config["groups"][url_pices[4]]["action"]["bri"]
                        del put_dictionary["bri_inc"]
                        put_dictionary.update({"bri": bridge_config["groups"][url_pices[4]]["action"]["bri"]})
                        for light in bridge_config["groups"][url_pices[4]]["lights"]:
                            bridge_config["lights"][light]["state"].update(put_dictionary)
                            sendLightRequest(light, put_dictionary)
                    elif "ct_inc" in put_dictionary:
                        bridge_config["groups"][url_pices[4]]["action"]["ct"] += int(put_dictionary["ct_inc"])
                        if bridge_config["groups"][url_pices[4]]["action"]["ct"] > 500:
                            bridge_config["groups"][url_pices[4]]["action"]["ct"] = 500
                        elif bridge_config["groups"][url_pices[4]]["action"]["ct"] < 153:
                            bridge_config["groups"][url_pices[4]]["action"]["ct"] = 153
                        bridge_config["groups"][url_pices[4]]["state"]["ct"] = bridge_config["groups"][url_pices[4]]["action"]["ct"]
                        del put_dictionary["ct_inc"]
                        put_dictionary.update({"ct": bridge_config["groups"][url_pices[4]]["action"]["ct"]})
                        for light in bridge_config["groups"][url_pices[4]]["lights"]:
                            bridge_config["lights"][light]["state"].update(put_dictionary)
                            sendLightRequest(light, put_dictionary)
                    elif "scene_inc" in put_dictionary:
                        switchScene(url_pices[4], put_dictionary["scene_inc"])
                    elif url_pices[4] == "0": #if group is 0 the scene applied to all lights
                        for light in bridge_config["lights"].keys():
                            if "virtual_light" not in bridge_config["alarm_config"] or light != bridge_config["alarm_config"]["virtual_light"]:
                                bridge_config["lights"][light]["state"].update(put_dictionary)
                                sendLightRequest(light, put_dictionary)
                        for group in bridge_config["groups"].keys():
                            bridge_config["groups"][group][url_pices[5]].update(put_dictionary)
                            if "on" in put_dictionary:
                                bridge_config["groups"][group]["state"]["any_on"] = put_dictionary["on"]
                                bridge_config["groups"][group]["state"]["all_on"] = put_dictionary["on"]
                    else: # the state is applied to particular group (url_pices[4])
                        if "on" in put_dictionary:
                            bridge_config["groups"][url_pices[4]]["state"]["any_on"] = put_dictionary["on"]
                            bridge_config["groups"][url_pices[4]]["state"]["all_on"] = put_dictionary["on"]
                        bridge_config["groups"][url_pices[4]][url_pices[5]].update(put_dictionary)
                        #send all unique ip's in thread mode for speed
                        lightsIps = []
                        processedLights = []
                        for light in bridge_config["groups"][url_pices[4]]["lights"]:
                            bridge_config["lights"][light]["state"].update(put_dictionary)
                            if bridge_config["lights_address"][light]["ip"] not in lightsIps:
                                lightsIps.append(bridge_config["lights_address"][light]["ip"])
                                processedLights.append(light)
                                Thread(target=sendLightRequest, args=[light, put_dictionary]).start()
                        #now send the rest of the requests in non threaded mode
                        for light in bridge_config["groups"][url_pices[4]]["lights"]:
                            if light not in processedLights:
                                sendLightRequest(light, put_dictionary)
                elif url_pices[3] == "lights": #state is applied to a light
                    for key in put_dictionary.keys():
                        if key in ["ct", "xy"]: #colormode must be set by bridge
                            bridge_config["lights"][url_pices[4]]["state"]["colormode"] = key
                        elif key in ["hue", "sat"]:
                            bridge_config["lights"][url_pices[4]]["state"]["colormode"] = "hs"
                    updateGroupStats(url_pices[4])
                    sendLightRequest(url_pices[4], put_dictionary)
                if not url_pices[4] == "0": #group 0 is virtual, must not be saved in bridge configuration
                    try:
                        bridge_config[url_pices[3]][url_pices[4]][url_pices[5]].update(put_dictionary)
                    except KeyError:
                        bridge_config[url_pices[3]][url_pices[4]][url_pices[5]] = put_dictionary
                if url_pices[3] == "sensors" and url_pices[5] == "state":
                    current_time = datetime.now()
                    for key in put_dictionary.keys():
                        sensors_state[url_pices[4]]["state"].update({key: current_time})
                    rulesProcessor(url_pices[4], current_time)
                response_location = "/" + url_pices[3] + "/" + url_pices[4] + "/" + url_pices[5] + "/"
            if len(url_pices) == 7:
                try:
                    bridge_config[url_pices[3]][url_pices[4]][url_pices[5]][url_pices[6]].update(put_dictionary)
                except KeyError:
                    bridge_config[url_pices[3]][url_pices[4]][url_pices[5]][url_pices[6]] = put_dictionary
                bridge_config[url_pices[3]][url_pices[4]][url_pices[5]][url_pices[6]] = put_dictionary
                response_location = "/" + url_pices[3] + "/" + url_pices[4] + "/" + url_pices[5] + "/" + url_pices[6] + "/"
            response_dictionary = []
            for key, value in put_dictionary.items():
                response_dictionary.append({"success":{response_location + key: value}})
            self._set_end_headers(bytes(json.dumps(response_dictionary,separators=(',', ':')), "utf8"))
            print(json.dumps(response_dictionary, sort_keys=True, indent=4, separators=(',', ': ')))
        else:
            self._set_end_headers(bytes(json.dumps([{"error": {"type": 1, "address": self.path, "description": "unauthorized user" }}],separators=(',', ':')), "utf8"))

    def do_DELETE(self):
        self._set_headers()
        url_pices = self.path.split('/')
        if url_pices[2] in bridge_config["config"]["whitelist"]:
            if len(url_pices) == 6:
                del bridge_config[url_pices[3]][url_pices[4]][url_pices[5]]
            else:
                if url_pices[3] == "resourcelinks":
                    for link in bridge_config["resourcelinks"][url_pices[4]]["links"]:
                        link_pices = link.split('/')
                        if link.startswith("/rules") or link.startswith("/schedules"):
                            del bridge_config[link_pices[1]][link_pices[2]]
                        elif link.startswith("/sensors"):
                            if bridge_config[link_pices[1]][link_pices[2]]["type"] == "CLIPGenericStatus":
                                del bridge_config["sensors"][link_pices[2]]

                del bridge_config[url_pices[3]][url_pices[4]]
            if url_pices[3] == "lights":
                del bridge_config["lights_address"][url_pices[4]]
                for light in list(bridge_config["deconz"]["lights"]):
                    if bridge_config["deconz"]["lights"][light]["bridgeid"] == url_pices[4]:
                        del bridge_config["deconz"]["lights"][light]
            elif url_pices[3] == "sensors":
                for sensor in list(bridge_config["deconz"]["sensors"]):
                    if bridge_config["deconz"]["sensors"][sensor]["bridgeid"] == url_pices[4]:
                        del bridge_config["deconz"]["sensors"][sensor]
            self._set_end_headers(bytes(json.dumps([{"success": "/" + url_pices[3] + "/" + url_pices[4] + " deleted."}],separators=(',', ':')), "utf8"))