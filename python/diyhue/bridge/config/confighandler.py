"""
ConfigHandler
"""

class ConfigHandler(dict):
	def __init__(self, *args, **kwargs):
		if 'filename' not in kwargs:
			raise ValueError('Filename missing, '
				+ 'please include as keyworded argument (filename=x/x/x)')
		elif type(kwargs['filename']) is not str:
			raise ValueError('Filename must be of type str.')

		self.filename = kwargs['filename']

		self.__update(*args, **kwargs)

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
		Update
		"""
		pass

	def load(self, filename=None):
		"""
		Load config from file
		"""
		if not filename:
			filename = self.filename

		# TODO load config from file

	def save(self, filename=None):
		"""
		Save config to file
		"""
		if not filename:
			filename = self.filename

		# TODO spawn thread to save config