#!/usr/bin/python3
import logging
#SETUP LOGGER
logging.basicConfig(filename='logs/main.log', format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")

from trigger_load_balance import launch_trigger
from case_driver import launch_driver
from helper_functions import write_json
from helper_functions import create_csv
from request_functions import request_ml_avg_error
from request_functions import request_calc_avg_error
from balance_status import launch_balance_status_cases
from balance_status import launch_balance_status_sftp
from send_sftp import send_sftp
import json
import os
import sys
import requests
import time

#beam_balance_data.json 
"""
BEAM:
	FL: starts as current 30m avg and is updated with estimated load moved
	RL: starts as current 30m avg and is updated with estimated load moved
	initial_fl: 30m avg at the start of balance
	initial_rl: 30m avg at the start of balance
	logoffs: dict of IPs
		IP: [outbound15, inbound15, modcode, type(logoff, redirect), end_beam]
	redirects: dict of beams: dict of ips
		BEAM:
			IP: [outbound15, inbound15, modcode, type(logoff, redirect), end_beam]
	terminals: list of ips added to this beam
"""

def send_hb():
	hb_config = {}
	hb_config['origin'] = "Load Balance Tool"
	hb_config['timeout'] = 3900
	hb_config['tags'] = ["Middletown,Ubuntu,load_balance"]
	r = requests.post("http://192.168.220.35:8080/api/heartbeat",json=hb_config,timeout=10)
	logging.info('hb send. {}'.format(r))

def load_balance_main():

	config = json.load(open('config/script_config.json'))
	open_cases = json.load(open('res/open_cases.json'))
	last_balance = json.load(open('res/last_balance.json'))

	#CHECK ANY OPEN CASES FOR COMPLETION
	if open_cases and config['open_cases']:
		logging.info("checking case status")
		launch_balance_status_cases()
		
	sftp_time = json.load(open('res/sftp_time.json'))
	
	#IF SENDING EMAIL HANDLE CHECK DIFFERENTLY
	if sftp_time and config['send_sftp']:
		launch_balance_status_sftp()

	#TURN OFF ML IF THE MODEL IT PERFORMING POORLY
	if config['ml_model']:

		if request_ml_avg_error() > request_calc_avg_error():
			config['ml_model'] = False
			logging.info('ml auto turned off. MSE is too high')
			write_json('config/script_config.json', config)

	curr_time = int(time.time())

	#TRIGGER BALANCED IF CONTENDED
	triggered_balance = False

	#LIMITS MAX BALANCE FREQUENCY
	if curr_time - last_balance['timestamp'] > (config['frequency']*60 - 30):
		triggered_balance = launch_trigger()
	else:
		logging.info('frequency set to {} minutes'.format(config['frequency']))
		logging.info('balance again in {} seconds'.format((config['frequency']*60 - 30) - (curr_time - last_balance['timestamp'])))
		sys.exit()

	# OPEN CASES IF TRIGGERED
	if triggered_balance:

		last_balance['timestamp'] = curr_time
		write_json('res/last_balance.json', last_balance)

		if config['open_cases']:
			launch_driver()

		if config['send_sftp']:
			create_csv()
			send_sftp()

	else:
		logging.info("no beams contended")

	send_hb()

if __name__ == "__main__":
	load_balance_main()
