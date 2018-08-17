import json
import sys

def save_config(filename='/opt/hue-emulator/config.json', config):
    with open(filename, 'w') as fp:
        json.dump(config, fp, sort_keys=True, indent=4, separators=(',', ': '))

def load_config():
	try:
    	with open('/opt/hue-emulator/config.json', 'r') as fp:
        	bridge_config = json.load(fp)
        	print("Config loaded")
	except Exception:
    	print("CRITICAL! Config file was not loaded")
    	sys.exit(1)