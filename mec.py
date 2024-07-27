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

global demo
demo = 0
global mec_is_init
mec_is_init = 0
global dev_state
dev_state = DevState.WaitForDevice

def push_statistics() :
	global mec

	mec.set('/stats/connection_ok', Mec.stats.connection_ok)
	mec.set('/stats/connection_error', Mec.stats.connection_ko)
	mec.set('/stats/last_connection_errors', Mec.stats.last_connection_errors)
	mec.set('/stats/parse_error', Mec.stats.parse_error)
	mec.set('/stats/reconnect', Mec.stats.reconnect)


def read_settings() :
	parser = ConfigParser()
	parser.read('mec.ini')

	Mec.ip = parser.get('MEC', 'ip')
	Mec.url = parser.get('MEC', 'url')
	Mec.statusurl = parser.get('MEC', 'statusurl')
	Mec.user = parser.get('MEC', 'username')
	Mec.password = parser.get('MEC', 'password')
	Mec.intervall = float(parser.get('MEC', 'intervall'))

def mec_read_example(filename) :
	with open(filename) as f:
		data = json.load(f)
	#print(data)
	return data

def mec_parse_data( data ) :
	global mec, mec_is_init

	# read same variables only the first time
	if mec_is_init == 0:
		#mec.set('/ProductName', str(jsonstr['hardware']))
		mec_is_init = 1

	time = data['TIME']
	if Mec.stats.last_time == time:
		mec.inc('/stats/repeated_values')
		mec.inc('/stats/last_repeated_values')
		print('got repeated value')
	else:
		Mec.stats.last_time = time
		mec.set('/stats/last_repeated_values', 0)

		mec.set('/Ac/Power', (data['PT']))
		mec.set('/Ac/Current', (data['IN0']), 1)
		mec.set('/Ac/Voltage', (data['VT']))
		mec.set('/Ac/L1/Current', (data['IA']), 1)
		mec.set('/Ac/L1/Voltage', (data['VA']))
		mec.set('/Ac/L1/Power', (data['PA']))
		mec.set('/Ac/L2/Current', (data['IB']), 1)
		mec.set('/Ac/L2/Voltage', (data['VB']))
		mec.set('/Ac/L2/Power', (data['PB']))
		mec.set('/Ac/L3/Current', (data['IC']), 1)
		mec.set('/Ac/L3/Voltage', (data['VC']))
		mec.set('/Ac/L3/Power', (data['PC']))

		mec.set('/Ac/L1/Energy/Forward', (float(data['EFAA'])/1000), 2)
		mec.set('/Ac/L1/Energy/Reverse', (float(data['ERAA'])/1000), 2)
		mec.set('/Ac/L2/Energy/Forward', (float(data['EFAB'])/1000), 2)
		mec.set('/Ac/L2/Energy/Reverse', (float(data['ERAB'])/1000), 2)
		mec.set('/Ac/L3/Energy/Forward', (float(data['EFAC'])/1000), 2)
		mec.set('/Ac/L3/Energy/Reverse', (float(data['ERAC'])/1000), 2)

		mec.set('/Ac/Energy/Forward', (float(data['EFAT'])/1000), 2)
		mec.set('/Ac/Energy/Reverse', (float(data['ERAT'])/1000), 2)

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
	global mec
	if init:
		mec = VenusMeter('mec_tcp_50','tcp:' + Mec.ip, 50,'0',  str(jsonstr['hardware']), str(jsonstr['software']),'0.1')
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
	global dev_state, mec

	while run_event.is_set():
		print("Thread: doing")
		if dev_state >= DevState.Connected:
			push_statistics()
			intervall = mec.get('/Mgmt/intervall')
		else:
			intervall = Mec.intervall

		if Mec.stats.last_connection_errors > Mec.max_retries:
			print('Lost connection to mec, reset')
			dev_state = DevState.Connect
			Mec.stats.last_connection_errors = 0
			Mec.stats.reconnect += 1
			mec.set('/Connected', 0)
			mec.invalidate()

		if dev_state == DevState.WaitForDevice:
			if mec_read_status(init=1) == 0:
				dev_state = DevState.Connect
		elif dev_state == DevState.Connect:
			if mec_read_status(init=0) == 0:
				dev_state = DevState.Connected
				mec.validate()
				mec.set('/Connected', 1)
		elif dev_state == DevState.Connected:
			mec_read_data()
		else:
			dev_state = DevState.WaitForDevice

		time.sleep(intervall)
	return

DBusGMainLoop(set_as_default=True)
read_settings()
print("Using " + Mec.url + " user: " + Mec.user)

try:
	run_event = threading.Event()
	run_event.set()

	update_thread = threading.Thread(target=mec_update_cyclic, args=(run_event,))
	update_thread.start()

	mainloop = glib.MainLoop()
	mainloop.run()

except (KeyboardInterrupt, SystemExit):
	mainloop.quit()
	run_event.clear()
	update_thread.join()
	print("Host: KeyboardInterrupt")
