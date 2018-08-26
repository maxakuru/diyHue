"""
ConfigHandler
"""

class ConfigHandler(dict):
	def __init__(self, *args, **kwargs):
		super().__init__()
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
		# if not filename:
			# filename = self.filename

		# TODO load config from file

	def save(self, filename=None):
		"""
		Save config to file
		"""
		# if not filename:
			# filename = self.filename

		# TODO spawn thread to save config

	def update(*args, **kwds):
		'''od.update(E, **F) -> None.  Update od from dict/iterable E and F.

		If E is a dict instance, does:           for k in E: od[k] = E[k]
		If E has a .keys() method, does:         for k in E.keys(): od[k] = E[k]
		Or if E is an iterable of items, does:   for k, v in E: od[k] = v
		In either case, this is followed by:     for k, v in F.items(): od[k] = v

		'''
		if len(args) > 2:
			raise TypeError('update() takes at most 2 positional '
							'arguments (%d given)' % (len(args),))
		elif not args:
			raise TypeError('update() takes at least 1 argument (0 given)')
		self = args[0]
		# Make progressively weaker assumptions about "other"
		other = ()
		if len(args) == 2:
			other = args[1]
		if isinstance(other, dict):
			for key in other:
				self[key] = other[key]
		elif hasattr(other, 'keys'):
			for key in other.keys():
				self[key] = other[key]
		else:
			for key, value in other:
				self[key] = value
		for key, value in kwds.items():
			self[key] = value

	__update = update  # let subclasses override update without breaking __init__