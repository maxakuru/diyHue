#!/usr/bin/python3
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from time import strftime, sleep
from datetime import datetime, timedelta
from pprint import pprint
from subprocess import check_output, Popen
import json, socket, hashlib, random, sys, ssl
import requests
import urllib.request, urllib.parse
import base64
from threading import Thread
from collections import defaultdict
from uuid import getnode as get_mac
from urllib.parse import urlparse, parse_qs
from functions import *

update_lights_on_startup = False # if set to true all lights will be updated with last know state on startup.

mac = '%012x' % get_mac()

run_service = True

bridge_config = defaultdict(lambda:defaultdict(str))
new_lights = {}
sensors_state = {}


def updateConfig():
    for sensor in bridge_config["deconz"]["sensors"].keys():
        if "modelid" not in bridge_config["deconz"]["sensors"][sensor]:
            bridge_config["deconz"]["sensors"]["modelid"] = bridge_config["sensors"][bridge_config["deconz"]["sensors"][sensor]["bridgeid"]]["modelid"]
        if bridge_config["deconz"]["sensors"][sensor]["modelid"] == "TRADFRI motion sensor":
            if "lightsensor" not in bridge_config["deconz"]["sensors"][sensor]:
                bridge_config["deconz"]["sensors"][sensor]["lightsensor"] = "internal"
    for sensor in bridge_config["sensors"].keys():
        if bridge_config["sensors"][sensor]["type"] == "CLIPGenericStatus":
            bridge_config["sensors"][sensor]["state"]["status"] = 0


def entertainmentService():
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverSocket.bind(('127.0.0.1', 2101))
    fremeID = 0
    lightStatus = {}
    while True:
        data = serverSocket.recvfrom(106)[0]
        if data[:9].decode('utf-8') == "HueStream":
            if data[14] == 0: #rgb colorspace
                i = 16
                while i < len(data):
                    if data[i] == 0: #Type of device 0x00 = Light
                        lightId = data[i+1] * 256 + data[i+2]
                        if lightId != 0:
                            r = int((data[i+3] * 256 + data[i+4]) / 256)
                            g = int((data[i+5] * 256 + data[i+6]) / 256)
                            b = int((data[i+7] * 256 + data[i+7]) / 256)
                            if lightId not in lightStatus:
                                lightStatus[lightId] = {"on": False, "bri": 1}
                            if r == 0 and  g == 0 and  b == 0:
                                bridge_config["lights"][str(lightId)]["state"]["on"] = False
                            else:
                                bridge_config["lights"][str(lightId)]["state"].update({"on": True, "bri": int((r + g + b) / 3), "xy": convert_rgb_xy(r, g, b), "colormode": "xy"})
                            if bridge_config["lights_address"][str(lightId)]["protocol"] == "native":
                                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
                                sock.sendto(bytes([r]) + bytes([g]) + bytes([b]) + bytes([bridge_config["lights_address"][str(lightId)]["light_nr"] - 1]), (bridge_config["lights_address"][str(lightId)]["ip"], 2100))
                            else:
                                if fremeID == 24: # => every seconds, increase in case the destination device is overloaded
                                    if r == 0 and  g == 0 and  b == 0:
                                        if lightStatus[lightId]["on"]:
                                            sendLightRequest(str(lightId), {"on": False, "transitiontime": 3})
                                            lightStatus[lightId]["on"] = False
                                    elif lightStatus[lightId]["on"] == False:
                                        sendLightRequest(str(lightId), {"on": True, "transitiontime": 3})
                                        lightStatus[lightId]["on"] = True
                                    elif abs(int((r + b + g) / 3) - lightStatus[lightId]["bri"]) > 50: # to optimize, send brightness  only of difference is bigger than this value
                                        sendLightRequest(str(lightId), {"bri": int((r + b + g) / 3), "transitiontime": 3})
                                        lightStatus[lightId]["bri"] = int((r + b + g) / 3)
                                    else:
                                        sendLightRequest(str(lightId), {"xy": convert_rgb_xy(r, g, b), "transitiontime": 3})
                            fremeID += 1
                            if fremeID == 25:
                                fremeID = 0
                            updateGroupStats(lightId)
                        i = i + 9
            elif data[14] == 1: #cie colorspace
                i = 16
                while i < len(data):
                    if data[i] == 0: #Type of device 0x00 = Light
                        lightId = data[i+1] * 256 + data[i+2]
                        if lightId != 0:
                            x = (data[i+3] * 256 + data[i+4]) / 65535
                            y = (data[i+5] * 256 + data[i+6]) / 65535
                            bri = int((data[i+7] * 256 + data[i+7]) / 256)
                            if bri == 0:
                                bridge_config["lights"][str(lightId)]["state"]["on"] = False
                            else:
                                bridge_config["lights"][str(lightId)]["state"].update({"on": True, "bri": bri, "xy": [x,y], "colormode": "xy"})
                            if bridge_config["lights_address"][str(lightId)]["protocol"] == "native":
                                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
                                sock.sendto(bytes(convert_xy(x, y, bri)) + bytes([bridge_config["lights_address"][str(lightId)]["light_nr"] - 1]), (bridge_config["lights_address"][str(lightId)]["ip"], 2100))
                            else:
                                fremeID += 1
                                if fremeID == 24 : #24 = every seconds, increase in case the destination device is overloaded
                                    sendLightRequest(str(lightId), {"xy": [x,y]})
                                    fremeID = 0
                            updateGroupStats(lightId)


light_types = {"LCT015": {"state": {"on": False, "bri": 200, "hue": 0, "sat": 0, "xy": [0.0, 0.0], "ct": 461, "alert": "none", "effect": "none", "colormode": "ct", "reachable": True}, "type": "Extended color light", "swversion": "1.29.0_r21169"}, "LST002": {"state": {"on": False, "bri": 200, "hue": 0, "sat": 0, "xy": [0.0, 0.0], "ct": 461, "alert": "none", "effect": "none", "colormode": "ct", "reachable": True}, "type": "Color light", "swversion": "5.90.019950"}, "LWB010": {"state": {"on": False, "bri": 254,"alert": "none", "reachable": True}, "type": "Dimmable light", "swversion": "1.15.0_r18729"}, "LTW001": {"state": {"on": False, "colormode": "ct", "alert": "none", "reachable": True, "bri": 254, "ct": 230}, "type": "Color temperature light", "swversion": "5.50.1.19085"}, "Plug 01": {"state": {"on": False, "alert": "none", "reachable": True}, "type": "On/Off plug-in unit", "swversion": "V1.04.12"}}

def addTradfriDimmer(sensor_id, group_id):
    rules = [{ "actions":[{"address": "/groups/" + group_id + "/action", "body":{ "on":True, "bri":1 }, "method": "PUT" }], "conditions":[{ "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx"}, { "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "2002" }, { "address": "/groups/" + group_id + "/state/any_on", "operator": "eq", "value": "false" }], "name": "Remote " + sensor_id + " turn on" },{"actions":[{"address":"/groups/" + group_id + "/action", "body":{ "on": False}, "method":"PUT"}], "conditions":[{ "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }, { "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "4002" }, { "address": "/groups/" + group_id + "/state/any_on", "operator": "eq", "value": "true" }, { "address": "/groups/" + group_id + "/action/bri", "operator": "eq", "value": "1"}], "name":"Dimmer Switch " + sensor_id + " off"}, { "actions":[{ "address": "/groups/" + group_id + "/action", "body":{ "on":False }, "method": "PUT" }], "conditions":[{ "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }, { "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "3002" }, { "address": "/groups/" + group_id + "/state/any_on", "operator": "eq", "value": "true" }, { "address": "/groups/" + group_id + "/action/bri", "operator": "eq", "value": "1"}], "name": "Remote " + sensor_id + " turn off" }, { "actions": [{"address": "/groups/" + group_id + "/action", "body":{"bri_inc": 32, "transitiontime": 9}, "method": "PUT" }], "conditions": [{ "address": "/groups/" + group_id + "/state/any_on", "operator": "eq", "value": "true" },{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "2002" }, {"address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx"}], "name": "Dimmer Switch " + sensor_id + " rotate right"}, { "actions": [{"address": "/groups/" + group_id + "/action", "body":{"bri_inc": 56, "transitiontime": 9}, "method": "PUT" }], "conditions": [{ "address": "/groups/" + group_id + "/state/any_on", "operator": "eq", "value": "true" },{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "1002" }, {"address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx"}], "name": "Dimmer Switch " + sensor_id + " rotate fast right"}, {"actions": [{"address": "/groups/" + group_id + "/action", "body": {"bri_inc": -32, "transitiontime": 9}, "method": "PUT"}], "conditions": [{ "address": "/groups/" + group_id + "/action/bri", "operator": "gt", "value": "1"},{"address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "3002"}, {"address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx"}], "name": "Dimmer Switch " + sensor_id + " rotate left"}, {"actions": [{"address": "/groups/" + group_id + "/action", "body": {"bri_inc": -56, "transitiontime": 9}, "method": "PUT"}], "conditions": [{ "address": "/groups/" + group_id + "/action/bri", "operator": "gt", "value": "1"},{"address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "4002"}, {"address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx"}], "name": "Dimmer Switch " + sensor_id + " rotate left"}]
    resourcelinkId = next_free_id("resourcelinks")
    bridge_config["resourcelinks"][resourcelinkId] = {"classid": 15555,"description": "Rules for sensor " + sensor_id, "links": ["/sensors/" + sensor_id], "name": "Emulator rules " + sensor_id,"owner": list(bridge_config["config"]["whitelist"])[0]}
    for rule in rules:
        ruleId = next_free_id("rules")
        bridge_config["rules"][ruleId] = rule
        bridge_config["rules"][ruleId].update({"creationtime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "lasttriggered": None, "owner": list(bridge_config["config"]["whitelist"])[0], "recycle": True, "status": "enabled", "timestriggered": 0})
        bridge_config["resourcelinks"][resourcelinkId]["links"].append("/rules/" + ruleId);

def addTradfriCtRemote(sensor_id, group_id):
    rules = [{"actions": [{"address": "/groups/" + group_id + "/action","body": {"on": True},"method": "PUT"}],"conditions": [{"address": "/sensors/" + sensor_id + "/state/lastupdated","operator": "dx"},{"address": "/sensors/" + sensor_id + "/state/buttonevent","operator": "eq","value": "1002"},{"address": "/groups/" + group_id + "/state/any_on","operator": "eq","value": "false"}],"name": "Remote " + sensor_id + " button on"}, {"actions": [{"address": "/groups/" + group_id + "/action","body": {"on": False},"method": "PUT"}],"conditions": [{"address": "/sensors/" + sensor_id + "/state/lastupdated","operator": "dx"},{"address": "/sensors/" + sensor_id + "/state/buttonevent","operator": "eq","value": "1002"},{"address": "/groups/" + group_id + "/state/any_on","operator": "eq","value": "true"}],"name": "Remote " + sensor_id + " button off"},{ "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": 30, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "2002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " up-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": 56, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "2001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " up-long" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": -30, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "3002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " dn-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": -56, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "3001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " dn-long" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "ct_inc": 50, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "4002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ctl-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "ct_inc": 100, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "4001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ctl-long" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "ct_inc": -50, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "5002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ct-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "ct_inc": -100, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "5001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ct-long" }]
    resourcelinkId = next_free_id("resourcelinks")
    bridge_config["resourcelinks"][resourcelinkId] = {"classid": 15555,"description": "Rules for sensor " + sensor_id, "links": ["/sensors/" + sensor_id], "name": "Emulator rules " + sensor_id,"owner": list(bridge_config["config"]["whitelist"])[0]}
    for rule in rules:
        ruleId = next_free_id("rules")
        bridge_config["rules"][ruleId] = rule
        bridge_config["rules"][ruleId].update({"creationtime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "lasttriggered": None, "owner": list(bridge_config["config"]["whitelist"])[0], "recycle": True, "status": "enabled", "timestriggered": 0})
        bridge_config["resourcelinks"][resourcelinkId]["links"].append("/rules/" + ruleId);

def addTradfriSceneRemote(sensor_id, group_id):
    rules = [{"actions": [{"address": "/groups/" + group_id + "/action","body": {"on": True},"method": "PUT"}],"conditions": [{"address": "/sensors/" + sensor_id + "/state/lastupdated","operator": "dx"},{"address": "/sensors/" + sensor_id + "/state/buttonevent","operator": "eq","value": "1002"},{"address": "/groups/" + group_id + "/state/any_on","operator": "eq","value": "false"}],"name": "Remote " + sensor_id + " button on"}, {"actions": [{"address": "/groups/" + group_id + "/action","body": {"on": False},"method": "PUT"}],"conditions": [{"address": "/sensors/" + sensor_id + "/state/lastupdated","operator": "dx"},{"address": "/sensors/" + sensor_id + "/state/buttonevent","operator": "eq","value": "1002"},{"address": "/groups/" + group_id + "/state/any_on","operator": "eq","value": "true"}],"name": "Remote " + sensor_id + " button off"},{ "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": 30, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "2002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " up-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": 56, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "2001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " up-long" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": -30, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "3002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " dn-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "bri_inc": -56, "transitiontime": 9 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "3001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " dn-long" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "scene_inc": -1 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "4002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ctl-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "scene_inc": -1 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "4001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ctl-long" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "scene_inc": 1 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "5002" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ct-press" }, { "actions": [{ "address": "/groups/" + group_id + "/action", "body": { "scene_inc": 1 }, "method": "PUT" }], "conditions": [{ "address": "/sensors/" + sensor_id + "/state/buttonevent", "operator": "eq", "value": "5001" }, { "address": "/sensors/" + sensor_id + "/state/lastupdated", "operator": "dx" }], "name": "Dimmer Switch " + sensor_id + " ct-long" }]
    resourcelinkId = next_free_id("resourcelinks")
    bridge_config["resourcelinks"][resourcelinkId] = {"classid": 15555,"description": "Rules for sensor " + sensor_id, "links": ["/sensors/" + sensor_id], "name": "Emulator rules " + sensor_id,"owner": list(bridge_config["config"]["whitelist"])[0]}
    for rule in rules:
        ruleId = next_free_id("rules")
        bridge_config["rules"][ruleId] = rule
        bridge_config["rules"][ruleId].update({"creationtime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), "lasttriggered": None, "owner": list(bridge_config["config"]["whitelist"])[0], "recycle": True, "status": "enabled", "timestriggered": 0})
        bridge_config["resourcelinks"][resourcelinkId]["links"].append("/rules/" + ruleId);

def addHueMotionSensor(uniqueid, name="Entrance Lights sensor"):
    new_sensor_id = next_free_id("sensors")
    if uniqueid == "":
        if len(new_sensor_id) == 1:
            uniqueid = "0" + new_sensor_id + ":0f:12:23:34:45"
        else:
            uniqueid = new_sensor_id + ":0f:12:23:34:45"
    bridge_config["sensors"][next_free_id("sensors")] = {"name": "Hue temperature sensor 1", "uniqueid": uniqueid + ":56:d0:5b-02-0402", "type": "ZLLTemperature", "swversion": "6.1.0.18912", "state": {"temperature": None, "lastupdated": "none"}, "manufacturername": "Philips", "config": {"on": False, "battery": 100, "reachable": True, "alert":"none", "ledindication": False, "usertest": False, "pending": []}, "modelid": "SML001"}
    motion_sensor = next_free_id("sensors")
    bridge_config["sensors"][motion_sensor] = {"name": name, "uniqueid": uniqueid + ":56:d0:5b-02-0406", "type": "ZLLPresence", "swversion": "6.1.0.18912", "state": {"lastupdated": "none", "presence": None}, "manufacturername": "Philips", "config": {"on": False,"battery": 100,"reachable": True, "alert": "lselect", "ledindication": False, "usertest": False, "sensitivity": 2, "sensitivitymax": 2,"pending": []}, "modelid": "SML001"}
    bridge_config["sensors"][next_free_id("sensors")] = {"name": "Hue ambient light sensor", "uniqueid": uniqueid + ":56:d0:5b-02-0400", "type": "ZLLLightLevel", "swversion": "6.1.0.18912", "state": {"dark": True, "daylight": False, "lightlevel": 6000, "lastupdated": "none"}, "manufacturername": "Philips", "config": {"on": False,"battery": 100, "reachable": True, "alert": "none", "tholddark": 21597, "tholdoffset": 7000, "ledindication": False, "usertest": False, "pending": []}, "modelid": "SML001"}
    return(motion_sensor)

def addHueSwitch(uniqueid, sensorsType):
    new_sensor_id = next_free_id("sensors")
    if uniqueid == "":
        uniqueid = "00:00:00:00:00:40:" + new_sensor_id + ":83-f2"
    bridge_config["sensors"][new_sensor_id] = {"state": {"buttonevent": 0, "lastupdated": "none"}, "config": {"on": True, "battery": 100, "reachable": True}, "name": "Dimmer Switch" if sensorsType == "ZLLSwitch" else "Tap Switch", "type": sensorsType, "modelid": "RWL021" if sensorsType == "ZLLSwitch" else "ZGPSWITCH", "manufacturername": "Philips", "swversion": "5.45.1.17846" if sensorsType == "ZLLSwitch" else "", "uniqueid": uniqueid}
    return(new_sensor_id)

def sendEmail(triggered_sensor):
    import smtplib

    TEXT = "Sensor " + triggered_sensor + " was triggered while the alarm is active"
    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (bridge_config["alarm_config"]["mail_from"], ", ".join(bridge_config["alarm_config"]["mail_recipients"]), bridge_config["alarm_config"]["mail_subject"], TEXT)
    try:
        server_ssl = smtplib.SMTP_SSL(bridge_config["alarm_config"]["smtp_server"], bridge_config["alarm_config"]["smtp_port"])
        server_ssl.ehlo() # optional, called by login()
        server_ssl.login(bridge_config["alarm_config"]["mail_username"], bridge_config["alarm_config"]["mail_password"])
        server_ssl.sendmail(bridge_config["alarm_config"]["mail_from"], bridge_config["alarm_config"]["mail_recipients"], message)
        server_ssl.close()
        print("successfully sent the mail")
        return True
    except:
        print("failed to send mail")
        return False

def next_free_id(element):
    i = 1
    while (str(i)) in bridge_config[element]:
        i += 1
    return str(i)

def load_alarm_config():  #load and configure alarm virtual light
    if bridge_config["alarm_config"]["mail_username"] != "":
        print("E-mail account configured")
        if "virtual_light" not in bridge_config["alarm_config"]:
            print("Send test email")
            if sendEmail("dummy test"):
                print("Mail succesfully sent\nCreate alarm virtual light")
                new_light_id = next_free_id("lights")
                bridge_config["lights"][new_light_id] = {"state": {"on": False, "bri": 200, "hue": 0, "sat": 0, "xy": [0.690456, 0.295907], "ct": 461, "alert": "none", "effect": "none", "colormode": "xy", "reachable": True}, "type": "Extended color light", "name": "Alarm", "uniqueid": "1234567ffffff", "modelid": "LLC012", "swversion": "66009461"}
                bridge_config["alarm_config"]["virtual_light"] = new_light_id
            else:
                print("Mail test failed")
load_alarm_config()

def generateSensorsState():
    for sensor in bridge_config["sensors"]:
        if sensor not in sensors_state and "state" in bridge_config["sensors"][sensor]:
            sensors_state[sensor] = {"state": {}}
            for key in bridge_config["sensors"][sensor]["state"].keys():
                if key in ["lastupdated", "presence", "flag", "dark", "daylight", "status"]:
                    sensors_state[sensor]["state"].update({key: datetime.now()})

generateSensorsState()

def getIpAddress():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]

ip_pices = getIpAddress().split(".")
bridge_config["config"]["ipaddress"] = getIpAddress()
bridge_config["config"]["gateway"] = ip_pices[0] + "." +  ip_pices[1] + "." + ip_pices[2] + ".1"
bridge_config["config"]["mac"] = mac[0] + mac[1] + ":" + mac[2] + mac[3] + ":" + mac[4] + mac[5] + ":" + mac[6] + mac[7] + ":" + mac[8] + mac[9] + ":" + mac[10] + mac[11]
bridge_config["config"]["bridgeid"] = (mac[:6] + 'FFFE' + mac[6:]).upper()


def schedulerProcessor():
    while run_service:
        for schedule in bridge_config["schedules"].keys():
            delay = 0
            if bridge_config["schedules"][schedule]["status"] == "enabled":
                if bridge_config["schedules"][schedule]["localtime"][-9:-8] == "A":
                    delay = random.randrange(0, int(bridge_config["schedules"][schedule]["localtime"][-8:-6]) * 3600 + int(bridge_config["schedules"][schedule]["localtime"][-5:-3]) * 60 + int(bridge_config["schedules"][schedule]["localtime"][-2:]))
                    schedule_time = bridge_config["schedules"][schedule]["localtime"][:-9]
                else:
                    schedule_time = bridge_config["schedules"][schedule]["localtime"]
                if schedule_time.startswith("W"):
                    pices = schedule_time.split('/T')
                    if int(pices[0][1:]) & (1 << 6 - datetime.today().weekday()):
                        if pices[1] == datetime.now().strftime("%H:%M:%S"):
                            print("execute schedule: " + schedule + " withe delay " + str(delay))
                            sendRequest(bridge_config["schedules"][schedule]["command"]["address"], bridge_config["schedules"][schedule]["command"]["method"], json.dumps(bridge_config["schedules"][schedule]["command"]["body"]), 1, delay)
                elif schedule_time.startswith("PT"):
                    timmer = schedule_time[2:]
                    (h, m, s) = timmer.split(':')
                    d = timedelta(hours=int(h), minutes=int(m), seconds=int(s))
                    if bridge_config["schedules"][schedule]["starttime"] == (datetime.utcnow() - d).strftime("%Y-%m-%dT%H:%M:%S"):
                        print("execute timmer: " + schedule + " withe delay " + str(delay))
                        sendRequest(bridge_config["schedules"][schedule]["command"]["address"], bridge_config["schedules"][schedule]["command"]["method"], json.dumps(bridge_config["schedules"][schedule]["command"]["body"]), 1, delay)
                        bridge_config["schedules"][schedule]["status"] = "disabled"
                else:
                    if schedule_time == datetime.now().strftime("%Y-%m-%dT%H:%M:%S"):
                        print("execute schedule: " + schedule + " withe delay " + str(delay))
                        sendRequest(bridge_config["schedules"][schedule]["command"]["address"], bridge_config["schedules"][schedule]["command"]["method"], json.dumps(bridge_config["schedules"][schedule]["command"]["body"]), 1, delay)
                        if bridge_config["schedules"][schedule]["autodelete"]:
                            del bridge_config["schedules"][schedule]
        if (datetime.now().strftime("%M:%S") == "00:10"): #auto save configuration every hour
            saveConfig()
            Thread(target=daylightSensor).start()
            if (datetime.now().strftime("%H") == "23" and datetime.now().strftime("%A") == "Sunday"): #backup config every Sunday at 23:00:10
                saveConfig("config-backup-" + datetime.now().strftime("%Y-%m-%d") + ".json")
        sleep(1)

def switchScene(group, direction):
    group_scenes = []
    current_position = -1
    possible_current_position = -1 # used in case the brigtness was changes and will be no perfect match (scene lightstates vs light states)
    break_next = False
    for scene in bridge_config["scenes"]:
        if bridge_config["groups"][group]["lights"][0] in bridge_config["scenes"][scene]["lights"]:
            group_scenes.append(scene)
            if break_next: # don't lose time as this is the scene we need
                break
            is_current_scene = True
            is_possible_current_scene = True
            for light in bridge_config["scenes"][scene]["lightstates"]:
                for key in bridge_config["scenes"][scene]["lightstates"][light].keys():
                    if key == "xy":
                        if not bridge_config["scenes"][scene]["lightstates"][light]["xy"][0] == bridge_config["lights"][light]["state"]["xy"][0] and not bridge_config["scenes"][scene]["lightstates"][light]["xy"][1] == bridge_config["lights"][light]["state"]["xy"][1]:
                            is_current_scene = False
                    else:
                        if not bridge_config["scenes"][scene]["lightstates"][light][key] == bridge_config["lights"][light]["state"][key]:
                            is_current_scene = False
                            if not key == "bri":
                                is_possible_current_scene = False
            if is_current_scene:
                current_position = len(group_scenes) -1
                if direction == -1 and len(group_scenes) != 1:
                    break
                elif len(group_scenes) != 1:
                    break_next = True
            elif  is_possible_current_scene:
                possible_current_position = len(group_scenes) -1

    matched_scene = ""
    if current_position + possible_current_position == -2:
        print("current scene not found, reset to zero")
        if len(group_scenes) != 0:
            matched_scene = group_scenes[0]
        else:
            print("error, no scenes found")
            return
    elif current_position != -1:
        if len(group_scenes) -1 < current_position + direction:
            matched_scene = group_scenes[0]
        else:
            matched_scene = group_scenes[current_position + direction]
    elif possible_current_position != -1:
        if len(group_scenes) -1 < possible_current_position + direction:
            matched_scene = group_scenes[0]
        else:
            matched_scene = group_scenes[possible_current_position + direction]
    print("matched scene " + bridge_config["scenes"][matched_scene]["name"])

    for light in bridge_config["scenes"][matched_scene]["lights"]:
        bridge_config["lights"][light]["state"].update(bridge_config["scenes"][matched_scene]["lightstates"][light])
        if "xy" in bridge_config["scenes"][matched_scene]["lightstates"][light]:
            bridge_config["lights"][light]["state"]["colormode"] = "xy"
        elif "ct" in bridge_config["scenes"][matched_scene]["lightstates"][light]:
            bridge_config["lights"][light]["state"]["colormode"] = "ct"
        elif "hue" or "sat" in bridge_config["scenes"][matched_scene]["lightstates"][light]:
            bridge_config["lights"][light]["state"]["colormode"] = "hs"
        sendLightRequest(light, bridge_config["scenes"][matched_scene]["lightstates"][light])
        updateGroupStats(light)


def checkRuleConditions(rule, sensor, current_time, ignore_ddx=False):
    ddx = 0
    sensor_found = False
    ddx_sensor = []
    for condition in bridge_config["rules"][rule]["conditions"]:
        url_pices = condition["address"].split('/')
        if url_pices[1] == "sensors" and sensor == url_pices[2]:
            sensor_found = True
        if condition["operator"] == "eq":
            if condition["value"] == "true":
                if not bridge_config[url_pices[1]][url_pices[2]][url_pices[3]][url_pices[4]]:
                    return [False, 0]
            elif condition["value"] == "false":
                if bridge_config[url_pices[1]][url_pices[2]][url_pices[3]][url_pices[4]]:
                    return [False, 0]
            else:
                if not int(bridge_config[url_pices[1]][url_pices[2]][url_pices[3]][url_pices[4]]) == int(condition["value"]):
                    return [False, 0]
        elif condition["operator"] == "gt":
            if not int(bridge_config[url_pices[1]][url_pices[2]][url_pices[3]][url_pices[4]]) > int(condition["value"]):
                return [False, 0]
        elif condition["operator"] == "lt":
            if not int(bridge_config[url_pices[1]][url_pices[2]][url_pices[3]][url_pices[4]]) < int(condition["value"]):
                return [False, 0]
        elif condition["operator"] == "dx":
            if not sensors_state[url_pices[2]][url_pices[3]][url_pices[4]] == current_time:
                return [False, 0]
        elif condition["operator"] == "in":
            periods = condition["value"].split('/')
            if condition["value"][0] == "T":
                timeStart = datetime.strptime(periods[0], "T%H:%M:%S").time()
                timeEnd = datetime.strptime(periods[1], "T%H:%M:%S").time()
                now_time = datetime.now().time()
                if timeStart < timeEnd:
                    if not timeStart <= now_time <= timeEnd:
                        return [False, 0]
                else:
                    if not (timeStart <= now_time or now_time <= timeEnd):
                        return [False, 0]
        elif condition["operator"] == "ddx" and ignore_ddx is False:
            if not sensors_state[url_pices[2]][url_pices[3]][url_pices[4]] == current_time:
                    return [False, 0]
            else:
                ddx = int(condition["value"][2:4]) * 3600 + int(condition["value"][5:7]) * 60 + int(condition["value"][-2:])
                ddx_sensor = url_pices


    if sensor_found:
        return [True, ddx, ddx_sensor]
    else:
        return [False]

def ddxRecheck(rule, sensor, current_time, ddx_delay, ddx_sensor):
    for x in range(ddx_delay):
        if current_time != sensors_state[ddx_sensor[2]][ddx_sensor[3]][ddx_sensor[4]]:
            print("ddx rule " + rule + " canceled after " + str(x) + " seconds")
            return # rule not valid anymore because sensor state changed while waiting for ddx delay
        sleep(1)
    current_time = datetime.now()
    rule_state = checkRuleConditions(rule, sensor, current_time, True)
    if rule_state[0]: #if all conditions are meet again
        print("delayed rule " + rule + " is triggered")
        bridge_config["rules"][rule]["lasttriggered"] = current_time.strftime("%Y-%m-%dT%H:%M:%S")
        bridge_config["rules"][rule]["timestriggered"] += 1
        for action in bridge_config["rules"][rule]["actions"]:
            sendRequest("/api/" + bridge_config["rules"][rule]["owner"] + action["address"], action["method"], json.dumps(action["body"]))

def rulesProcessor(sensor, current_time):
    bridge_config["config"]["localtime"] = current_time.strftime("%Y-%m-%dT%H:%M:%S") #required for operator dx to address /config/localtime
    actionsToExecute = []
    for rule in bridge_config["rules"].keys():
        if bridge_config["rules"][rule]["status"] == "enabled":
            rule_result = checkRuleConditions(rule, sensor, current_time)
            if rule_result[0]:
                if rule_result[1] == 0: #is not ddx rule
                    print("rule " + rule + " is triggered")
                    bridge_config["rules"][rule]["lasttriggered"] = current_time.strftime("%Y-%m-%dT%H:%M:%S")
                    bridge_config["rules"][rule]["timestriggered"] += 1
                    for action in bridge_config["rules"][rule]["actions"]:
                        actionsToExecute.append(action)
                else: #if ddx rule
                    print("ddx rule " + rule + " will be re validated after " + str(rule_result[1]) + " seconds")
                    Thread(target=ddxRecheck, args=[rule, sensor, current_time, rule_result[1], rule_result[2]]).start()
    for action in actionsToExecute:
        sendRequest("/api/" +    list(bridge_config["config"]["whitelist"])[0] + action["address"], action["method"], json.dumps(action["body"]))

def sendRequest(url, method, data, timeout=3, delay=0):
    if delay != 0:
        sleep(delay)
    if not url.startswith( 'http://' ):
        url = "http://127.0.0.1" + url
    head = {"Content-type": "application/json"}
    if method == "POST":
        response = requests.post(url, data=bytes(data, "utf8"), timeout=timeout, headers=head)
        return response.text
    elif method == "PUT":
        response = requests.put(url, data=bytes(data, "utf8"), timeout=timeout, headers=head)
        return response.text
    elif method == "GET":
        response = requests.get(url, timeout=timeout, headers=head)
        return response.text
    elif method == "TCP":
        if "//" in url: # cutting out the http://
            http, url = url.split("//",1)
        # yeelight uses different functions for each action, so it has to check for each function
        # see page 9 http://www.yeelight.com/download/Yeelight_Inter-Operation_Spec.pdf
        # check if hue wants to change brightness
        for key, value in json.loads(data).items():
            sendToYeelight(url, key, value)

def sendToYeelight(url, api_method, param):
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(5)
        tcp_socket.connect((url, int(55443)))
        msg = json.dumps({"id": 1, "method": api_method, "params": param}) + "\r\n"
        tcp_socket.send(msg.encode())
        tcp_socket.close()
    except Exception as e:
        print ("Unexpected error:", e)


def sendLightRequest(light, data):
    payload = {}
    if light in bridge_config["lights_address"]:
        if bridge_config["lights_address"][light]["protocol"] == "native": #ESP8266 light or strip
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
                payload.clear() #setting brightnes will turn on the ligh even if there was a request to power off
                payload["5850"] = 0
            elif "5850" in payload and "5851" in payload: #when setting brightness don't send also power on command
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

def updateGroupStats(light): #set group stats based on lights status in that group
    for group in bridge_config["groups"]:
        if "lights" in bridge_config["groups"][group] and light in bridge_config["groups"][group]["lights"]:
            for key, value in bridge_config["lights"][light]["state"].items():
                if key in ["bri", "xy", "ct", "hue", "sat"]:
                    bridge_config["groups"][group]["action"][key] = value
            any_on = False
            all_on = True
            for group_light in bridge_config["groups"][group]["lights"]:
                if bridge_config["lights"][light]["state"]["on"] == True:
                    any_on = True
                else:
                    all_on = False
            bridge_config["groups"][group]["state"] = {"any_on": any_on, "all_on": all_on,}
            bridge_config["groups"][group]["action"]["on"] = any_on


def discoverYeelight():
    group = ("239.255.255.250", 1982)
    message = "\r\n".join([
        'M-SEARCH * HTTP/1.1',
        'HOST: 239.255.255.250:1982',
        'MAN: "ssdp:discover"',
        'ST: wifi_bulb'])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(3)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.sendto(message.encode(), group)
    while True:
        try:
            response = sock.recv(1024).decode('utf-8').split("\r\n")
            properties = {"rgb": False, "ct": False}
            for line in response:
                if line[:2] == "id":
                    properties["id"] = line[4:]
                elif line[:3] == "rgb":
                    properties["rgb"] = True
                elif line[:2] == "ct":
                    properties["ct"] = True
                elif line[:8] == "Location":
                    properties["ip"] = line.split(":")[2][2:]
                elif line[:4] == "name":
                    properties["name"] = line[6:]
            device_exist = False
            for light in bridge_config["lights_address"].keys():
                if bridge_config["lights_address"][light]["protocol"] == "yeelight" and  bridge_config["lights_address"][light]["id"] == properties["id"]:
                    device_exist = True
                    bridge_config["lights_address"][light]["ip"] = properties["ip"]
                    print("light id " + properties["id"] + " already exist, updating ip...")
                    break
            if (not device_exist):
                light_name = "YeeLight id " + properties["id"][-8:] if properties["name"] == "" else properties["name"]
                print("Add YeeLight: " + properties["id"])
                modelid = "LWB010"
                if properties["rgb"]:
                    modelid = "LCT015"
                elif properties["ct"]:
                    modelid = "LTW001"
                new_light_id = next_free_id("lights")
                bridge_config["lights"][new_light_id] = {"state": light_types[modelid]["state"], "type": light_types[modelid]["type"], "name": light_name, "uniqueid": "4a:e0:ad:7f:cf:" + str(random.randrange(0, 99)) + "-1", "modelid": modelid, "manufacturername": "Philips", "swversion": light_types[modelid]["swversion"]}
                new_lights.update({new_light_id: {"name": light_name}})
                bridge_config["lights_address"][new_light_id] = {"ip": properties["ip"], "id": properties["id"], "protocol": "yeelight"}


        except socket.timeout:
            print('Yeelight search end')
            sock.close()
            break


def scanForLights(): #scan for ESP8266 lights and strips
    Thread(target=discoverYeelight).start()
    #return all host that listen on port 80
    device_ips = check_output("nmap  " + getIpAddress() + "/24 -p80 --open -n | grep report | cut -d ' ' -f5", shell=True).decode('utf-8').split("\n")
    pprint(device_ips)
    del device_ips[-1] #delete last empty element in list
    for ip in device_ips:
        try:
            if ip != getIpAddress():
                response = requests.get("http://" + ip + "/detect", timeout=3)
                if response.status_code == 200:
                    device_data = json.loads(response.text)
                    pprint(device_data)
                    if "hue" in device_data:
                        print(ip + " is a hue " + device_data['hue'])
                        device_exist = False
                        for light in bridge_config["lights"].keys():
                            if bridge_config["lights"][light]["uniqueid"].startswith( device_data["mac"] ):
                                device_exist = True
                                bridge_config["lights_address"][light]["ip"] = ip
                        if not device_exist:
                            light_name = "Hue " + device_data["hue"] + " " + device_data["modelid"]
                            if "name" in device_data:
                                light_name = device_data["name"]
                            print("Add new light: " + light_name)
                            for x in range(1, int(device_data["lights"]) + 1):
                                new_light_id = next_free_id("lights")
                                bridge_config["lights"][new_light_id] = {"state": light_types[device_data["modelid"]]["state"], "type": light_types[device_data["modelid"]]["type"], "name": light_name if x == 1 else light_name + " " + str(x), "uniqueid": device_data["mac"] + "-" + str(x), "modelid": device_data["modelid"], "manufacturername": "Philips", "swversion": light_types[device_data["modelid"]]["swversion"]}
                                new_lights.update({new_light_id: {"name": light_name if x == 1 else light_name + " " + str(x)}})
                                bridge_config["lights_address"][new_light_id] = {"ip": ip, "light_nr": x, "protocol": "native"}
        except Exception as e:
            print("ip " + ip + " is unknow device, " + str(e))
    scanDeconz()
    scanTradfri()
    saveConfig()


def syncWithLights(): #update Hue Bridge lights states
    while True:
        print("sync with lights")
        for light in bridge_config["lights_address"]:
            try:
                if bridge_config["lights_address"][light]["protocol"] == "native":
                    light_data = json.loads(sendRequest("http://" + bridge_config["lights_address"][light]["ip"] + "/get?light=" + str(bridge_config["lights_address"][light]["light_nr"]), "GET", "{}"))
                    bridge_config["lights"][light]["state"].update(light_data)
                elif bridge_config["lights_address"][light]["protocol"] == "hue":
                    light_data = json.loads(sendRequest("http://" + bridge_config["lights_address"][light]["ip"] + "/api/" + bridge_config["lights_address"][light]["username"] + "/lights/" + bridge_config["lights_address"][light]["light_id"], "GET", "{}"))
                    bridge_config["lights"][light]["state"].update(light_data["state"])
                elif bridge_config["lights_address"][light]["protocol"] == "ikea_tradfri":
                    light_data = json.loads(check_output("./coap-client-linux -m get -u \"" + bridge_config["lights_address"][light]["identity"] + "\" -k \"" + bridge_config["lights_address"][light]["preshared_key"] + "\" \"coaps://" + bridge_config["lights_address"][light]["ip"] + ":5684/15001/" + str(bridge_config["lights_address"][light]["device_id"]) +"\"", shell=True).decode('utf-8').split("\n")[3])
                    bridge_config["lights"][light]["state"]["on"] = bool(light_data["3311"][0]["5850"])
                    bridge_config["lights"][light]["state"]["bri"] = light_data["3311"][0]["5851"]
                    if "5706" in light_data["3311"][0]:
                        if light_data["3311"][0]["5706"] == "f5faf6":
                            bridge_config["lights"][light]["state"]["ct"] = 170
                        elif light_data["3311"][0]["5706"] == "f1e0b5":
                            bridge_config["lights"][light]["state"]["ct"] = 320
                        elif light_data["3311"][0]["5706"] == "efd275":
                            bridge_config["lights"][light]["state"]["ct"] = 470
                    else:
                        bridge_config["lights"][light]["state"]["ct"] = 470
                elif bridge_config["lights_address"][light]["protocol"] == "milight":
                    light_data = json.loads(sendRequest("http://" + bridge_config["lights_address"][light]["ip"] + "/gateways/" + bridge_config["lights_address"][light]["device_id"] + "/" + bridge_config["lights_address"][light]["mode"] + "/" + str(bridge_config["lights_address"][light]["group"]), "GET", "{}"))
                    if light_data["state"] == "ON":
                        bridge_config["lights"][light]["state"]["on"] = True
                    else:
                        bridge_config["lights"][light]["state"]["on"] = False
                    if "brightness" in light_data:
                        bridge_config["lights"][light]["state"]["bri"] = light_data["brightness"]
                    if "color_temp" in light_data:
                        bridge_config["lights"][light]["state"]["colormode"] = "ct"
                        bridge_config["lights"][light]["state"]["ct"] = light_data["color_temp"] * 1.6
                    elif "bulb_mode" in light_data and light_data["bulb_mode"] == "color":
                        bridge_config["lights"][light]["state"]["colormode"] = "xy"
                        bridge_config["lights"][light]["state"]["xy"] = convert_rgb_xy(light_data["color"]["r"], light_data["color"]["g"], light_data["color"]["b"])
                elif bridge_config["lights_address"][light]["protocol"] == "yeelight": #getting states from the yeelight
                    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    tcp_socket.settimeout(5)
                    tcp_socket.connect((bridge_config["lights_address"][light]["ip"], int(55443)))
                    msg=json.dumps({"id": 1, "method": "get_prop", "params":["power","bright"]}) + "\r\n"
                    tcp_socket.send(msg.encode())
                    data = tcp_socket.recv(16 * 1024)
                    light_data = json.loads(data[:-2].decode("utf8"))["result"]
                    if light_data[0] == "on": #powerstate
                        bridge_config["lights"][light]["state"]["on"] = True
                    else:
                        bridge_config["lights"][light]["state"]["on"] = False
                    bridge_config["lights"][light]["state"]["bri"] = int(int(light_data[1]) * 2.54)
                    msg_mode=json.dumps({"id": 1, "method": "get_prop", "params":["color_mode"]}) + "\r\n"
                    tcp_socket.send(msg_mode.encode())
                    data = tcp_socket.recv(16 * 1024)
                    if json.loads(data[:-2].decode("utf8"))["result"][0] == "1": #rgb mode
                        msg_rgb=json.dumps({"id": 1, "method": "get_prop", "params":["rgb"]}) + "\r\n"
                        tcp_socket.send(msg_rgb.encode())
                        data = tcp_socket.recv(16 * 1024)
                        hue_data = json.loads(data[:-2].decode("utf8"))["result"]
                        hex_rgb = "%6x" % int(json.loads(data[:-2].decode("utf8"))["result"][0])
                        r = hex_rgb[:2]
                        if r == "  ":
                            r = "00"
                        g = hex_rgb[3:4]
                        if g == "  ":
                            g = "00"
                        b = hex_rgb[-2:]
                        if b == "  ":
                            b = "00"
                        bridge_config["lights"][light]["state"]["xy"] = convert_rgb_xy(int(r,16), int(g,16), int(b,16))
                        bridge_config["lights"][light]["state"]["colormode"] = "xy"
                    elif json.loads(data[:-2].decode("utf8"))["result"][0] == "2": #ct mode
                        msg_ct=json.dumps({"id": 1, "method": "get_prop", "params":["ct"]}) + "\r\n"
                        tcp_socket.send(msg_ct.encode())
                        data = tcp_socket.recv(16 * 1024)
                        bridge_config["lights"][light]["state"]["ct"] =  int(1000000 / int(json.loads(data[:-2].decode("utf8"))["result"][0]))
                        bridge_config["lights"][light]["state"]["colormode"] = "ct"

                    elif json.loads(data[:-2].decode("utf8"))["result"][0] == "3": #ct mode
                        msg_hsv=json.dumps({"id": 1, "method": "get_prop", "params":["hue","sat"]}) + "\r\n"
                        tcp_socket.send(msg_hsv.encode())
                        data = tcp_socket.recv(16 * 1024)
                        hue_data = json.loads(data[:-2].decode("utf8"))["result"]
                        bridge_config["lights"][light]["state"]["hue"] = int(hue_data[0] * 182)
                        bridge_config["lights"][light]["state"]["sat"] = int(int(hue_data[1]) * 2.54)
                        bridge_config["lights"][light]["state"]["colormode"] = "hs"
                    tcp_socket.close()

                elif bridge_config["lights_address"][light]["protocol"] == "domoticz": #domoticz protocol
                    light_data = json.loads(sendRequest("http://" + bridge_config["lights_address"][light]["ip"] + "/json.htm?type=devices&rid=" + bridge_config["lights_address"][light]["light_id"], "GET", "{}"))
                    if light_data["result"][0]["Status"] == "Off":
                         bridge_config["lights"][light]["state"]["on"] = False
                    else:
                         bridge_config["lights"][light]["state"]["on"] = True
                    bridge_config["lights"][light]["state"]["bri"] = str(round(float(light_data["result"][0]["Level"])/100*255))

                bridge_config["lights"][light]["state"]["reachable"] = True
                updateGroupStats(light)
            except:
                bridge_config["lights"][light]["state"]["reachable"] = False
                bridge_config["lights"][light]["state"]["on"] = False
                print("light " + light + " is unreachable")
        sleep(10) #wait at last 10 seconds before next sync
        i = 0
        while i < 300: #sync with lights every 300 seconds or instant if one user is connected
            for user in bridge_config["config"]["whitelist"].keys():
                if bridge_config["config"]["whitelist"][user]["last use date"] == datetime.now().strftime("%Y-%m-%dT%H:%M:%S"):
                    i = 300
                    break
            sleep(1)



def longPressButton(sensor, buttonevent):
    print("long press detected")
    sleep(1)
    while bridge_config["sensors"][sensor]["state"]["buttonevent"] == buttonevent:
        print("still pressed")
        current_time =  datetime.now()
        sensors_state[sensor]["state"]["lastupdated"] = current_time
        rulesProcessor(sensor, current_time)
        sleep(0.9)
    return


def motionDetected(sensor):
    print("monitoring esp8266 motion sensor")
    while bridge_config["sensors"][sensor]["state"]["presence"] == True:
        if datetime.utcnow() - datetime.strptime(bridge_config["sensors"][sensor]["state"]["lastupdated"], "%Y-%m-%dT%H:%M:%S") > timedelta(seconds=30):
            bridge_config["sensors"][sensor]["state"]["presence"] = False
            bridge_config["sensors"][sensor]["state"]["lastupdated"] =  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            current_time =  datetime.now()
            sensors_state[sensor]["state"]["presence"] = current_time
            rulesProcessor(sensor, current_time)
        sleep(1)
    return


def scanTradfri():
    if "tradfri" in bridge_config:
        tradri_devices = json.loads(check_output("./coap-client-linux -m get -u \"" + bridge_config["tradfri"]["identity"] + "\" -k \"" + bridge_config["tradfri"]["psk"] + "\" \"coaps://" + bridge_config["tradfri"]["ip"] + ":5684/15001\"", shell=True).decode('utf-8').split("\n")[3])
        pprint(tradri_devices)
        lights_found = 0
        for device in tradri_devices:
            device_parameters = json.loads(check_output("./coap-client-linux -m get -u \"" + bridge_config["tradfri"]["identity"] + "\" -k \"" + bridge_config["tradfri"]["psk"] + "\" \"coaps://" + bridge_config["tradfri"]["ip"] + ":5684/15001/" + str(device) +"\"", shell=True).decode('utf-8').split("\n")[3])
            if "3311" in device_parameters:
                new_light = True
                for light in bridge_config["lights_address"]:
                    if bridge_config["lights_address"][light]["protocol"] == "ikea_tradfri" and bridge_config["lights_address"][light]["device_id"] == device:
                        new_light = False
                        break
                if new_light:
                    lights_found += 1
                    #register new tradfri lightdevice_id
                    print("register tradfi light " + device_parameters["9001"])
                    new_light_id = next_free_id("lights")
                    bridge_config["lights"][new_light_id] = {"state": {"on": False, "bri": 200, "hue": 0, "sat": 0, "xy": [0.0, 0.0], "ct": 461, "alert": "none", "effect": "none", "colormode": "ct", "reachable": True}, "type": "Extended color light", "name": device_parameters["9001"], "uniqueid": "1234567" + str(device), "modelid": "LLM010", "swversion": "66009461"}
                    new_lights.update({new_light_id: {"name": device_parameters["9001"]}})
                    bridge_config["lights_address"][new_light_id] = {"device_id": device, "preshared_key": bridge_config["tradfri"]["psk"], "identity": bridge_config["tradfri"]["identity"], "ip": bridge_config["tradfri"]["ip"], "protocol": "ikea_tradfri"}
        return lights_found
    else:
        return 0

def websocketClient():
    from ws4py.client.threadedclient import WebSocketClient
    class EchoClient(WebSocketClient):
        def opened(self):
            self.send("hello")

        def closed(self, code, reason=None):
            print(("deconz websocket disconnected", code, reason))
            del bridge_config["deconz"]["websocketport"]

        def received_message(self, m):
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

    try:
        ws = EchoClient('ws://127.0.0.1:' + str(bridge_config["deconz"]["websocketport"]))
        ws.connect()
        ws.run_forever()
    except KeyboardInterrupt:
        ws.close()

def scanDeconz():
    if not bridge_config["deconz"]["enabled"]:
        if "username" not in bridge_config["deconz"]:
            try:
                registration = json.loads(sendRequest("http://127.0.0.1:" + str(bridge_config["deconz"]["port"]) + "/api", "POST", "{\"username\": \"283145a4e198cc6535\", \"devicetype\":\"Hue Emulator\"}"))
            except:
                print("registration fail, is the link button pressed?")
                return
            if "success" in registration[0]:
                bridge_config["deconz"]["username"] = registration[0]["success"]["username"]
                bridge_config["deconz"]["enabled"] = True
    if "username" in bridge_config["deconz"]:
        deconz_config = json.loads(sendRequest("http://127.0.0.1:" + str(bridge_config["deconz"]["port"]) + "/api/" + bridge_config["deconz"]["username"] + "/config", "GET", "{}"))
        bridge_config["deconz"]["websocketport"] = deconz_config["websocketport"]

        #lights
        deconz_lights = json.loads(sendRequest("http://127.0.0.1:" + str(bridge_config["deconz"]["port"]) + "/api/" + bridge_config["deconz"]["username"] + "/lights", "GET", "{}"))
        for light in deconz_lights:
            if light not in bridge_config["deconz"]["lights"]:
                new_light_id = next_free_id("lights")
                print("register new light " + new_light_id)
                bridge_config["lights"][new_light_id] = deconz_lights[light]
                bridge_config["lights_address"][new_light_id] = {"username": bridge_config["deconz"]["username"], "light_id": light, "ip": "127.0.0.1:" + str(bridge_config["deconz"]["port"]), "protocol": "deconz"}
                bridge_config["deconz"]["lights"][light] = {"bridgeid": new_light_id}
            else: #temporary patch for config compatibility with new release
                bridge_config["deconz"]["lights"][light]["modelid"] = deconz_lights[light]["modelid"]
                bridge_config["deconz"]["lights"][light]["type"] = deconz_lights[light]["type"]



        #sensors
        deconz_sensors = json.loads(sendRequest("http://127.0.0.1:" + str(bridge_config["deconz"]["port"]) + "/api/" + bridge_config["deconz"]["username"] + "/sensors", "GET", "{}"))
        for sensor in deconz_sensors:
            if sensor not in bridge_config["deconz"]["sensors"]:
                new_sensor_id = next_free_id("sensors")
                if deconz_sensors[sensor]["modelid"] in ["TRADFRI remote control", "TRADFRI wireless dimmer"]:
                    print("register new " + deconz_sensors[sensor]["modelid"])
                    bridge_config["sensors"][new_sensor_id] = {"config": deconz_sensors[sensor]["config"], "manufacturername": deconz_sensors[sensor]["manufacturername"], "modelid": deconz_sensors[sensor]["modelid"], "name": deconz_sensors[sensor]["name"], "state": deconz_sensors[sensor]["state"], "type": deconz_sensors[sensor]["type"], "uniqueid": deconz_sensors[sensor]["uniqueid"]}
                    if "swversion" in  deconz_sensors[sensor]:
                        bridge_config["sensors"][new_sensor_id]["swversion"] = deconz_sensors[sensor]["swversion"]
                    bridge_config["deconz"]["sensors"][sensor] = {"bridgeid": new_sensor_id, "modelid": deconz_sensors[sensor]["modelid"]}
                elif deconz_sensors[sensor]["modelid"] == "TRADFRI motion sensor":
                    print("register TRADFRI motion sensor as Philips Motion Sensor")
                    newMotionSensorId = addHueMotionSensor("", deconz_sensors[sensor]["name"])
                    bridge_config["deconz"]["sensors"][sensor] = {"bridgeid": newMotionSensorId, "triggered": False, "modelid": deconz_sensors[sensor]["modelid"], "lightsensor": "internal"}

                elif deconz_sensors[sensor]["modelid"] == "lumi.sensor_motion.aq2":
                    if deconz_sensors[sensor]["type"] == "ZHALightLevel":
                        print("register new Xiaomi light sensor")
                        bridge_config["sensors"][new_sensor_id] = {"name": "Hue ambient light sensor 1", "uniqueid": "00:17:88:01:02:" + deconz_sensors[sensor]["uniqueid"][12:], "type": "ZLLLightLevel", "swversion": "6.1.0.18912", "state": {"dark": True, "daylight": False, "lightlevel": 6000, "lastupdated": "none"}, "manufacturername": "Philips", "config": {"on": False,"battery": 100, "reachable": True, "alert": "none", "tholddark": 21597, "tholdoffset": 7000, "ledindication": False, "usertest": False, "pending": []}, "modelid": "SML001"}
                        bridge_config["sensors"][next_free_id("sensors")] = {"name": "Hue temperature sensor 1", "uniqueid": "00:17:88:01:02:" + deconz_sensors[sensor]["uniqueid"][12:-1] + "2", "type": "ZLLTemperature", "swversion": "6.1.0.18912", "state": {"temperature": None, "lastupdated": "none"}, "manufacturername": "Philips", "config": {"on": False, "battery": 100, "reachable": True, "alert":"none", "ledindication": False, "usertest": False, "pending": []}, "modelid": "SML001"}
                        bridge_config["deconz"]["sensors"][sensor] = {"bridgeid": new_sensor_id, "modelid": deconz_sensors[sensor]["modelid"]}
                    elif deconz_sensors[sensor]["type"] == "ZHAPresence":
                        print("register new Xiaomi motion sensor")
                        bridge_config["sensors"][new_sensor_id] = {"name": deconz_sensors[sensor]["name"], "uniqueid": "00:17:88:01:02:" + deconz_sensors[sensor]["uniqueid"][12:], "type": "ZLLPresence", "swversion": "6.1.0.18912", "state": {"lastupdated": "none", "presence": None}, "manufacturername": "Philips", "config": {"on": False,"battery": 100,"reachable": True, "alert": "lselect", "ledindication": False, "usertest": False, "sensitivity": 2, "sensitivitymax": 2,"pending": []}, "modelid": "SML001"}
                        bridge_config["deconz"]["sensors"][sensor] = {"bridgeid": new_sensor_id, "modelid": deconz_sensors[sensor]["modelid"]}
                elif deconz_sensors[sensor]["modelid"] == "lumi.sensor_motion":
                    print("register Xiaomi Motion sensor w/o light sensor")
                    newMotionSensorId = addHueMotionSensor("", deconz_sensors[sensor]["name"])
                    bridge_config["deconz"]["sensors"][sensor] = {"bridgeid": newMotionSensorId, "triggered": False, "modelid": deconz_sensors[sensor]["modelid"]}
                else:
                    bridge_config["sensors"][new_sensor_id] = deconz_sensors[sensor]
                    bridge_config["deconz"]["sensors"][sensor] = {"bridgeid": new_sensor_id}
            else: #temporary patch for config compatibility with new release
                bridge_config["deconz"]["sensors"][sensor]["modelid"] = deconz_sensors[sensor]["modelid"]
                bridge_config["deconz"]["sensors"][sensor]["type"] = deconz_sensors[sensor]["type"]
        generateSensorsState()

        if "websocketport" in bridge_config["deconz"]:
            print("Starting deconz websocket")
            Thread(target=websocketClient).start()


def updateAllLights():
    ## apply last state on startup to all bulbs, usefull if there was a power outage
    for light in bridge_config["lights_address"]:
        payload = {}
        payload["on"] = bridge_config["lights"][light]["state"]["on"]
        if payload["on"] and "bri" in bridge_config["lights"][light]["state"]:
            payload["bri"] = bridge_config["lights"][light]["state"]["bri"]
        sendLightRequest(light, payload)
        sleep(0.5)
        print("update status for light " + light)

def daylightSensor():
    if bridge_config["sensors"]["1"]["modelid"] != "PHDL00" or not bridge_config["sensors"]["1"]["config"]["configured"]:
        return

    import pytz, astral
    from astral import Astral, Location
    a = Astral()
    a.solar_depression = 'civil'
    loc = Location(('Current', bridge_config["config"]["timezone"].split("/")[1], float(bridge_config["sensors"]["1"]["config"]["lat"][:-1]), float(bridge_config["sensors"]["1"]["config"]["long"][:-1]), bridge_config["config"]["timezone"], 0))
    sun = loc.sun(date=datetime.now(), local=True)
    deltaSunset = sun['sunset'].replace(tzinfo=None) - datetime.now()
    deltaSunrise = sun['sunrise'].replace(tzinfo=None) - datetime.now()
    deltaSunsetOffset = deltaSunset.total_seconds() + bridge_config["sensors"]["1"]["config"]["sunsetoffset"] * 60
    deltaSunriseOffset = deltaSunrise.total_seconds() + bridge_config["sensors"]["1"]["config"]["sunriseoffset"] * 60
    print("deltaSunsetOffset: " + str(deltaSunsetOffset))
    print("deltaSunriseOffset: " + str(deltaSunriseOffset))
    current_time =  datetime.now()
    if deltaSunsetOffset > 0 and deltaSunsetOffset < 3600:
        print("will start the sleep for sunset")
        sleep(deltaSunsetOffset)
        print("sleep finish at " + current_time.strftime("%Y-%m-%dT%H:%M:%S"))
        bridge_config["sensors"]["1"]["state"] = {"daylight":False,"lastupdated": current_time.strftime("%Y-%m-%dT%H:%M:%S")}
        sensors_state["1"]["state"]["daylight"] = current_time
        rulesProcessor("1", current_time)
    if deltaSunriseOffset > 0 and deltaSunriseOffset < 3600:
        print("will start the sleep for sunrise")
        sleep(deltaSunriseOffset)
        print("sleep finish at " + current_time.strftime("%Y-%m-%dT%H:%M:%S"))
        bridge_config["sensors"]["1"]["state"] = {"daylight":True,"lastupdated": current_time.strftime("%Y-%m-%dT%H:%M:%S")}
        sensors_state["1"]["state"]["daylight"] = current_time
        rulesProcessor("1", current_time)
    if deltaSunriseOffset < 0 and deltaSunsetOffset > 0:
        bridge_config["sensors"]["1"]["state"] = {"daylight":True,"lastupdated": current_time.strftime("%Y-%m-%dT%H:%M:%S")}
        print("set daylight sensor to true")
    else:
        bridge_config["sensors"]["1"]["state"] = {"daylight":False,"lastupdated": current_time.strftime("%Y-%m-%dT%H:%M:%S")}
        print("set daylight sensor to false")

if __name__ == "__main__":
    updateConfig()
    if bridge_config["deconz"]["enabled"]:
        scanDeconz()
    try:
        if update_lights_on_startup:
            updateAllLights()
        Thread(target=ssdpSearch, args=[getIpAddress(), mac]).start()
        Thread(target=ssdpBroadcast, args=[getIpAddress(), mac]).start()
        Thread(target=schedulerProcessor).start()
        Thread(target=syncWithLights).start()
        Thread(target=entertainmentService).start()
        Thread(target=run, args=[False]).start()
        Thread(target=run, args=[True]).start()
        Thread(target=daylightSensor).start()
        while True:
            sleep(10)
    except Exception as e:
        print("server stopped " + str(e))
    finally:
        run_service = False
        saveConfig()
        print ('config saved')
