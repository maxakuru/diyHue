"""
SchedulerController

"""

from time import sleep

from ..controller import ControllerThread

class SchedulerController(ControllerThread):
	def __init__(self, emulator, ip, mac):
		super().__init__()
		self._emulator = emulator
		self._ip = ip
		self._mac = mac
		self.alive = True

	@property
	def emulator(self):
		return self._emulator
	@property
	def ip(self):
		return self._ip
	@property
	def mac(self):
		return self._mac
		

	def run(self):
		"""
		Main thread loop.
		"""
		while self.alive:
			sleep(10)

	def close(self):
		self.alive = False