import json
import sys

class ConfigHandler(object):
	"""
	Handles the config; loading, saving, setting of fields.
	"""
	def __init__(self, filename='/opt/hue-emulator/config.json'):
		self.filename = filename

		self._config = {}
		self._dirty = False

	@property
	def config(self):
		return self._config

	@property
	def dirty(self):
		return self._dirty
	@dirty.setter
	def dirty(self, val):
		self._dirty = val

	def save_config(self, filename=None):
		if not filename:
			filename = self.filename
	    with open(filename, 'w') as fp:
	        json.dump(config, fp, sort_keys=True, indent=4, separators=(',', ': '))

	def load_config(self, filename=None):
		if not filename:
			filename = self.filename
		try:
	    	with open(filename, 'r') as fp:
	        	bridge_config = json.load(fp)
	        	print("Config loaded")
		except Exception:
	    	print("CRITICAL! Config file was not loaded")
	    	sys.exit(1)