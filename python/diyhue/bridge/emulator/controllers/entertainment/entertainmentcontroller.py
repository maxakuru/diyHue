"""
EntertainmentController

"""

from time import sleep

from ..controller import Controller

class EntertainmentController(Controller):
	def __init__(self, ip, mac):
		super().__init__()
		self.ip = ip
		self.mac = mac
		self.alive = True

	def run(self):
		"""
		Main thread loop.
		"""
		while self.alive:
			sleep(10)

	def close(self):
		self.alive = False