#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#vi: set autoindent noexpandtab tabstop=4 shiftwidth=4

from dbus.mainloop.glib import DBusGMainLoop
try:
	import gobject
	from gobject import idle_add
except:
	from gi.repository import GObject as gobject
	from gi.repository.GObject import idle_add
import dbus
import dbus.service
import inspect
import pprint
import os
import sys


# velib path
sys.path.insert(1, os.path.join(os.path.dirname(__file__), './velib_python'))
from vedbus import VeDbusService

#def main(argv):
#	global dbusObjects
class VenusMeter :
	devname = []
	pversion = []
	connection = []
	instance = []
	product = []
	firmwarev = []
	dbusservice = []
	serial = []
	disable_charge_state_old = 0
	disable_feedin_state_old = 0

	def __init__(self, dev, connection, instance, serial, product, firmwarev, pversion) :
		#VERSION = '0.1'

		print(__file__ + " starting up")
		self.devname = dev
		self.connection = connection
		self.instance = instance
		self.serial = serial
		self.product = product
		self.firmwarev = firmwarev
		self.pversion = pversion
		# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
		#DBusGMainLoop(set_as_default=True)

	def invalidate(self) :
		self.set('/Ac/L1/Power',[])
		self.set('/Ac/L2/Power',[])
		self.set('/Ac/L3/Power',[])
		self.set('/Ac/Power',[])
		self.set('/Connected',0)
		self.dbusservice.__del__()  # explicitly call __del__(), instead of waiting for gc
		self.dbusservice = 0
		print('Removed device ' + self.devname + ' from dbus')

	def validate(self) :
		#Put ourselves on to the dbus
		self.dbusservice = VeDbusService('com.victronenergy.grid.' + self.devname)

		# Most simple and short way to add an object with an initial value of 5.
		#	dbusservice.add_path('/Ac/Power', value=1000, description='Total power', writeable=False)
		#	dbusservice.add_path('/DeviceType', value=1000, description='Total power', writeable=False)
		# Add objects required by ve-api
		self.dbusservice.add_path('/Mgmt/ProcessName', __file__)
		self.dbusservice.add_path('/Mgmt/ProcessVersion', self.pversion)
		self.dbusservice.add_path('/Mgmt/Connection', self.connection) # todo
		self.dbusservice.add_path('/DeviceInstance', self.instance)
		self.dbusservice.add_path('/ProductId', 0xB023) # 0xB012 ?
		self.dbusservice.add_path('/ProductName', self.product)
		self.dbusservice.add_path('/DeviceType', 345)
		#self.dbusservice.add_path('/CustomName', "PLC Mec meter")
		self.dbusservice.add_path('/FirmwareVersion', self.firmwarev)
		self.dbusservice.add_path('/Serial', self.serial)
		self.dbusservice.add_path('/Role', 'grid')
		self.dbusservice.add_path('/Position', 0)
		self.dbusservice.add_path('/Connected', 1, writeable=True)
		self.dbusservice.add_path('/ErrorCode', '(0) No Error')
		self.dbusservice.add_path('/UpdateIndex', 0, writeable=True)

		_kwh = lambda p, v: (str(v) + 'KWh')
		_a = lambda p, v: (str(v) + 'A')
		_w = lambda p, v: (str(v) + 'W')
		_v = lambda p, v: (str(v) + 'V')
		_s = lambda p, v: (str(v) + 's')
		_x = lambda p, v: (str(v))

		self.dbusservice.add_path('/Ac/Energy/Forward', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/Energy/Reverse', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L1/Current', None, gettextcallback=_a)
		self.dbusservice.add_path('/Ac/L1/Energy/Forward', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L1/Energy/Reverse', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L1/Power', None, gettextcallback=_w)
		self.dbusservice.add_path('/Ac/L1/Voltage', None, gettextcallback=_v)
		self.dbusservice.add_path('/Ac/L2/Current', None, gettextcallback=_a)
		self.dbusservice.add_path('/Ac/L2/Energy/Forward', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L2/Energy/Reverse', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L2/Power', None, gettextcallback=_w)
		self.dbusservice.add_path('/Ac/L2/Voltage', None, gettextcallback=_v)
		self.dbusservice.add_path('/Ac/L3/Current', None, gettextcallback=_a)
		self.dbusservice.add_path('/Ac/L3/Energy/Forward', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L3/Energy/Reverse', None, gettextcallback=_kwh)
		self.dbusservice.add_path('/Ac/L3/Power', None, gettextcallback=_w)
		self.dbusservice.add_path('/Ac/L3/Voltage', None, gettextcallback=_v)
		self.dbusservice.add_path('/Ac/Power', None, gettextcallback=_w)
		self.dbusservice.add_path('/Ac/Current', None, gettextcallback=_a)
		self.dbusservice.add_path('/Ac/Voltage', None, gettextcallback=_v)

		self.dbusservice.add_path('/stats/connection_ok', 0, gettextcallback=_x, writeable=True)
		self.dbusservice.add_path('/stats/connection_error', 0, gettextcallback=_x, writeable=True)
		self.dbusservice.add_path('/stats/parse_error', 0, gettextcallback=_x, writeable=True)
		self.dbusservice.add_path('/stats/repeated_values', 0, gettextcallback=_x, writeable=True)
		self.dbusservice.add_path('/stats/last_connection_errors', 0, gettextcallback=_x, writeable=True)
		self.dbusservice.add_path('/stats/last_repeated_values', 0, gettextcallback=_x, writeable=True)
		self.dbusservice.add_path('/stats/reconnect', 0, gettextcallback=_x)
		self.dbusservice.add_path('/Mgmt/intervall', 1, gettextcallback=_s, writeable=True)

		self.set('/Connected',1)
		print('Added device ' + self.devname + ' to dbus')

	def set(self, name, value, round_digits=0) :
		#print(str(name) + ' ' + str(value))
		if isinstance(value, float):
			self.dbusservice[name] = round(value, round_digits)
		else:
			self.dbusservice[name] = value

	def get(self, name) :
		v= self.dbusservice[name]
		return v

	def inc(self, name) :
		self.dbusservice[name] += 1
