"""
Controller base class
"""

from threading import Thread
from abc import ABC, abstractmethod

class Controller(ABC, Thread):

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