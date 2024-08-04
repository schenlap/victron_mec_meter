#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#vi: set autoindent noexpandtab tabstop=4 shiftwidth=4

import requests
from requests.auth import HTTPBasicAuth
import json
from configparser import ConfigParser
from venus_meter import VenusMeter

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib as glib
from gi.repository.GLib import idle_add

import dbus
import dbus.service
import inspect
import pprint
import os
import sys
import threading
import time

class DevState:
	WaitForDevice = 0
	Connect = 1
	Connected = 2

class DevStatistics:
	connection_ok = 0
	connection_ko = 0
	parse_error = 0
	last_connection_errors = 0 # reset every ok read
	last_time = 0
	reconnect = 0

class Mec:
	ip = []
	url = []
	urlstate = []
	user = []
	password = []
	stats = DevStatistics
	intervall = []
	max_retries = 10

class Vz:
	ip = []
	stats = DevStatistics
	uuid_import = []
	uuid_export = []

class MeterConfig:
	NONE = 0
	VZ_PUSH = 1
	MEC = 2

meterconfig = MeterConfig.NONE

global demo
demo = 0
global mec_is_init
mec_is_init = 0
global dev_state
dev_state = DevState.WaitForDevice

def push_statistics() :
	global meter

	meter.set('/stats/connection_ok', Mec.stats.connection_ok)
	meter.set('/stats/connection_error', Mec.stats.connection_ko)
	meter.set('/stats/last_connection_errors', Mec.stats.last_connection_errors)
	meter.set('/stats/parse_error', Mec.stats.parse_error)
	meter.set('/stats/reconnect', Mec.stats.reconnect)


def read_settings() :
	global meterconfig
	parser = ConfigParser()
	parser.read('meter.ini')

	if parser.has_section("VOLKSZAEHLER"):
		Vz.ip = parser.get('VOLKSZAEHLER', 'ip')
		Vz.uuid_import = parser.get('VOLKSZAEHLER', 'uuid_import')
		Vz.uuid_export = parser.get('VOLKSZAEHLER', 'uuid_export')
		meterconfig = MeterConfig.VZ_PUSH

	elif parser.has_section("MEC"):
		Mec.ip = parser.get('MEC', 'ip')
		Mec.url = parser.get('MEC', 'url')
		Mec.statusurl = parser.get('MEC', 'statusurl')
		Mec.user = parser.get('MEC', 'username')
		Mec.password = parser.get('MEC', 'password')
		Mec.intervall = float(parser.get('MEC', 'intervall'))
		meterconfig = MeterConfig.MEC
	else:
		raise Exception("no valid config found")

def mec_read_example(filename) :
	with open(filename) as f:
		data = json.load(f)
	#print(data)
	return data

def mec_parse_data( data ) :
	global meter, mec_is_init

	# read same variables only the first time
	if mec_is_init == 0:
		#meter.set('/ProductName', str(jsonstr['hardware']))
		mec_is_init = 1

	time = data['TIME']
	if Mec.stats.last_time == time:
		meter.inc('/stats/repeated_values')
		meter.inc('/stats/last_repeated_values')
		print('got repeated value')
	else:
		Mec.stats.last_time = time
		meter.set('/stats/last_repeated_values', 0)

		meter.set('/Ac/Power', (data['PT']))
		meter.set('/Ac/Current', (data['IN0']), 1)
		meter.set('/Ac/Voltage', (data['VT']))
		meter.set('/Ac/L1/Current', (data['IA']), 1)
		meter.set('/Ac/L1/Voltage', (data['VA']))
		meter.set('/Ac/L1/Power', (data['PA']))
		meter.set('/Ac/L2/Current', (data['IB']), 1)
		meter.set('/Ac/L2/Voltage', (data['VB']))
		meter.set('/Ac/L2/Power', (data['PB']))
		meter.set('/Ac/L3/Current', (data['IC']), 1)
		meter.set('/Ac/L3/Voltage', (data['VC']))
		meter.set('/Ac/L3/Power', (data['PC']))

		meter.set('/Ac/L1/Energy/Forward', (float(data['EFAA'])/1000), 2)
		meter.set('/Ac/L1/Energy/Reverse', (float(data['ERAA'])/1000), 2)
		meter.set('/Ac/L2/Energy/Forward', (float(data['EFAB'])/1000), 2)
		meter.set('/Ac/L2/Energy/Reverse', (float(data['ERAB'])/1000), 2)
		meter.set('/Ac/L3/Energy/Forward', (float(data['EFAC'])/1000), 2)
		meter.set('/Ac/L3/Energy/Reverse', (float(data['ERAC'])/1000), 2)

		meter.set('/Ac/Energy/Forward', (float(data['EFAT'])/1000), 2)
		meter.set('/Ac/Energy/Reverse', (float(data['ERAT'])/1000), 2)

		powertotal = data['PT']
		print("++++++++++")
		print("POWER Phase A: " + str(data['PA']) + "W")
		print("POWER Phase B: " + str(data['PB']) + "W")
		print("POWER Phase C: " + str(data['PC']) + "W")
		print("POWER Total: " + str(data['PT']) + "W")
		print("Time: " + str(data['TIME']) + "ms")
		print("MEC Status: " + str(data['STATUS']))

		#Mec.stats.parse_error += 1

def mec_data_read_cb( jsonstr ) :
	mec_parse_data ( jsonstr )
	return

def mec_status_read_cb( jsonstr, init) :
	global meter
	if init:
		meter = VenusMeter('mec_tcp_50','tcp:' + Mec.ip, 50,'0',  str(jsonstr['hardware']), str(jsonstr['software']),'0.1')
	return

def mec_read_data() :
	global demo

	err = 0
	if demo == 0:
		try:
			response = requests.get( Mec.url, verify=False, auth=HTTPBasicAuth(Mec.user, Mec.password), timeout=2)
			# For successful API call, response code will be 200 (OK)
			if(response.ok):
				#print("code:"+ str(response.status_code))
				#print("******************")
				#print("headers:"+ str(response.headers))
				#print("******************")
				#print("content text:"+ str(response.text))
				#print("******************")
				Mec.stats.connection_ok += 1
				if Mec.stats.last_connection_errors > 0:
					Mec.stats.last_connection_errors = 0
				mec_data_read_cb( jsonstr=response.json() )
				return 0
		except (requests.exceptions.HTTPError, requests.exceptions.RequestException):
			print('Error reading from ' + Mec.url)
			Mec.stats.connection_ko += 1
			Mec.stats.last_connection_errors += 1
			return 1
	else:
		data = mec_read_example("example_mec_data.json")
		Mec.stats.connection_ok += 1
		mec_data_read_cb(data)
		return 0
	return 0

def mec_read_status(init) :
	global demo

	if demo == 0:
		try:
			response = requests.get( Mec.statusurl ) # no auth an status read
		except requests.exceptions.HTTPError:
			print('Http Error reading from ' + Mec.statusurl)
			return 1
		except requests.exceptions.RequestException:
			print('Request Error reading from ' + Mec.statusurl)
			return 1

		# For successful API call, response code will be 200 (OK)
		if(response.ok):
			#print("code:"+ str(response.status_code))
			#print("******************")
			#print("headers:"+ str(response.headers))
			#print("******************")
			#print("content text:"+ str(response.text))
			#print("******************")
			mec_status_read_cb( jsonstr=response.json(), init=init )
			return 0
		else:
			print("Failure code:"+ str(response.status_code))
			return 1
	else:
		data = mec_read_example("example_mec_status.json")
		mec_status_read_cb(data, init)
		return 0
	return 0

def mec_update_cyclic(run_event) :
	global dev_state, meter

	while run_event.is_set():
		print("Thread: doing")
		if dev_state >= DevState.Connected:
			push_statistics()
			intervall = meter.get('/Mgmt/intervall')
		else:
			intervall = Mec.intervall

		if Mec.stats.last_connection_errors > Mec.max_retries:
			print('Lost connection to meter, reset')
			dev_state = DevState.Connect
			Mec.stats.last_connection_errors = 0
			Mec.stats.reconnect += 1
			meter.set('/Connected', 0)
			meter.invalidate()

		if dev_state == DevState.WaitForDevice:
			if mec_read_status(init=1) == 0:
				dev_state = DevState.Connect
		elif dev_state == DevState.Connect:
			if mec_read_status(init=0) == 0:
				dev_state = DevState.Connected
				meter.validate()
				meter.set('/Connected', 1)
		elif dev_state == DevState.Connected:
			mec_read_data()
		else:
			dev_state = DevState.WaitForDevice

		time.sleep(intervall)
	return

def start_test():
	vz_push.start_vz_push_receiver(Vz.ip, Vz.uuid_import, Vz.uuid_export)   # - .. export power

def vz_meter_update():
	e_forward = 10
	e_backward = 20
	updateIndex = 0
	while True:
		print('dbus meter update')
		if vz_push.disconnect:
			meter.set('/Connected', 0)
		else:
			meter.set('/Connected', 1)
		diff = vz_push.value_import - vz_push.value_export + vz_push.value_wp # + .. import
		v = 230
		i = diff / v
		if diff > 0:
			e_forward = e_forward + diff / 1000 / 3600
		else:
			e_backward = e_backward - diff / 1000 / 3600
		#i_phase = float(i * 1.2)
		i_phase = i
		#p_phase = float(diff / 3)
		p_phase = diff
		e_forward_phase = e_forward / 3
		e_backward_phase = e_backward / 3

		meter.set('/Ac/Power', (diff))
		meter.set('/Ac/Current', i, 1)
		meter.set('/Ac/Voltage', v)
		meter.set('/Ac/L1/Current', i_phase, 1)
		meter.set('/Ac/L1/Voltage', v)
		meter.set('/Ac/L1/Power', p_phase)
		#meter.set('/Ac/L2/Current', i_phase, 1)
		#meter.set('/Ac/L2/Voltage', v)
		#meter.set('/Ac/L2/Power', p_phase)
		#meter.set('/Ac/L3/Current', i_phase, 1)
		#meter.set('/Ac/L3/Voltage', v)
		#meter.set('/Ac/L3/Power', p_phase)
	
		meter.set('/Ac/L1/Energy/Forward', (e_forward_phase), 2)
		meter.set('/Ac/L1/Energy/Reverse', (e_forward_phase), 2)
		#meter.set('/Ac/L2/Energy/Forward', (e_forward_phase), 2)
		#meter.set('/Ac/L2/Energy/Reverse', (e_forward_phase), 2)
		#meter.set('/Ac/L3/Energy/Forward', (e_forward_phase), 2)
		#meter.set('/Ac/L3/Energy/Reverse', (e_forward_phase), 2)
	
		meter.set('/Ac/Energy/Forward', (e_forward), 2)
		meter.set('/Ac/Energy/Reverse', (e_forward), 2)
		meter.set('/UpdateIndex', updateIndex)
		updateIndex = updateIndex + 1
		if updateIndex > 255:
			updateIndex = 0
		#await asyncio.sleep(1.2)
		time.sleep(1.2)

DBusGMainLoop(set_as_default=True)
read_settings()
if meterconfig == MeterConfig.VZ_PUSH:
	print('Using VZ Push Server ' + Vz.ip)
	meter = VenusMeter('vz_tcp_50','tcp:' + Vz.ip, 50,'0',  'volkszaehler', '2.3.1','0.1')
	meter.validate()
	print('start push server')
	vz_client = threading.Thread(target=start_test)
	vz_client.start()
	print('started push server')
	vz_update = threading.Thread(target=vz_meter_update)
	vz_update.start()
	#asyncio.run(vz_meter_update)
	print('started meter update')
elif meterconfig == MeterConfig.MEC:
	print("Using " + Mec.url + " user: " + Mec.user)

try:
	run_event = threading.Event()
	run_event.set()

	if meterconfig == MeterConfig.MEC:
		update_thread = threading.Thread(target=mec_update_cyclic, args=(run_event,))
		update_thread.start()

	mainloop = glib.MainLoop()
	mainloop.run()

except (KeyboardInterrupt, SystemExit):
	mainloop.quit()
	run_event.clear()
	update_thread.join()
	print("Host: KeyboardInterrupt")
