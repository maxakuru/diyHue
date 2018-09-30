"""
ControllerThread base class
"""
from threading import Thread
from multiprocessing import Process
from abc import ABC, abstractmethod

class ControllerThread(ABC, Thread):

	@abstractmethod
	def run(self):
		"""
		Main thread
		"""
		pass

	@abstractmethod
	def close(self):
		"""
		Close
		Cleanup any variables.	
		"""
		pass

"""
ControllerProcess base class
"""
class ControllerProcess(ABC, Process):

	@abstractmethod
	def run(self):
		"""
		Main thread
		"""
		pass

	@abstractmethod
	def close(self):
		"""
		Close
		Cleanup any variables.	
		"""
		pass