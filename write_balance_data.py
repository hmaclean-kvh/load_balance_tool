#!/usr/bin/env python3
import json 
import requests
import time
from pprint import pprint
from helper_functions import get_terminal_list
from helper_functions import get_moved_bandwidth
from helper_functions import construct_feature_dic
from model_functions import *
from datetime import datetime
import math
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logger = logging.getLogger('balance_data_log')
logger.setLevel(logging.INFO)

def get_payload():
	balance_data = json.load(open('data/balance_data.json'))
	timestamp = '%.0f' % time.time()
	payload = ""

	date = datetime.now().timetuple()
	month = date[1]
	day = date[2]
	hour = date[3]

	model = load_regression_model()

	moved_bandwidth = get_moved_bandwidth(balance_data)

	script_config = json.load(open('config/script_config.json'))

	method = "calculation"

	if script_config['ml_model']:
		method = 'ml_model'

	for beam in balance_data:
		iteration = balance_data[beam]['iterations']
		initial_rl = balance_data[beam]['initial_rl']
		initial_fl = balance_data[beam]['initial_fl']
		predicted_rl = balance_data[beam]['RL']
		predicted_fl = balance_data[beam]['FL']
		actual_rl = balance_data[beam]['actual_rl']
		actual_fl = balance_data[beam]['actual_fl']
		terminal_list = get_terminal_list(balance_data[beam])
		terminal_status_list = balance_data[beam]['terminal_status']
		# bursts = balance_data[beam]['bursts']
		# burst_cap = balance_data[beam]['burst_cap']
		# congestion = balance_data[beam]['congestion']

		if "ml_rl_prediction" in balance_data[beam]:
			ml_rl_prediction = balance_data[beam]['ml_rl_prediction']
			payload += "ml_rl_prediction,beam={},iteration={} value={} {}\n".format(beam, iteration, ml_rl_prediction, timestamp)
			payload += "ml_rl_squared_error,beam={},iteration={} value={} {}\n".format(beam, iteration, pow((ml_rl_prediction-actual_rl), 2), timestamp)
		if "ml_fl_prediction" in balance_data[beam]:
			ml_fl_prediction = balance_data[beam]['ml_fl_prediction']
			payload += "ml_fl_prediction,beam={},iteration={} value={} {}\n".format(beam, iteration, ml_fl_prediction, timestamp)
			payload += "ml_fl_squared_error,beam={},iteration={} value={} {}\n".format(beam, iteration, pow((ml_fl_prediction-actual_fl), 2), timestamp)
		if "calc_rl_prediction" in balance_data[beam]:
			calc_rl_prediction = balance_data[beam]['calc_rl_prediction']
			payload += "calc_rl_prediction,beam={},iteration={} value={} {}\n".format(beam, iteration, calc_rl_prediction, timestamp)
			payload += "calc_rl_squared_error,beam={},iteration={} value={} {}\n".format(beam, iteration, pow((calc_rl_prediction-actual_rl), 2), timestamp)
		if "calc_fl_prediction" in balance_data[beam]:
			calc_fl_prediction = balance_data[beam]['calc_fl_prediction']
			payload += "calc_fl_prediction,beam={},iteration={} value={} {}\n".format(beam, iteration, calc_fl_prediction, timestamp)
			payload += "calc_fl_squared_error,beam={},iteration={} value={} {}\n".format(beam, iteration, pow((calc_fl_prediction-actual_fl), 2), timestamp)

		# ^ is bitwise xor operator
		#SKIP BEAMS THAT WEREN'T EFFECTED BY BALANCE AND BEAMS THAT WERE BALANCED TO AND FROM
		# if (not terminal_list) ^ (len(balance_data[beam]['terminals']) == 0):

		for terminal in terminal_list:
			ip_address = terminal
			end_beam= terminal_list[terminal][4]
			inbound_15m_avg = terminal_list[terminal][1]
			outbound_15m_avg= terminal_list[terminal][0]
			inbound_2h_avg = terminal_list[terminal][6]
			outbound_2h_avg= terminal_list[terminal][5]
			mod_code = terminal_list[terminal][2]
			type1 = terminal_list[terminal][3]
			terminal_status = terminal_status_list[ip_address]
			payload += "inbound_15m_avg,ip_address={0},start_beam={1},end_beam={2},status={3},type={4},method={8},iteration={5} value={6} {7}\n".format(ip_address, beam, end_beam, terminal_status,type1, iteration, inbound_15m_avg, timestamp, method)
			payload += "outbound_15m_avg,ip_address={0},start_beam={1},end_beam={2},status={3},type={4},method={8},iteration={5} value={6} {7}\n".format(ip_address, beam, end_beam, terminal_status, type1, iteration, outbound_15m_avg, timestamp, method)
			payload += "inbound_2h_avg,ip_address={0},start_beam={1},end_beam={2},status={3},type={4},method={8},iteration={5} value={6} {7}\n".format(ip_address, beam, end_beam, terminal_status,type1, iteration, inbound_2h_avg, timestamp, method)
			payload += "outbound_2h_avg,ip_address={0},start_beam={1},end_beam={2},status={3},type={4},method={8},iteration={5} value={6} {7}\n".format(ip_address, beam, end_beam, terminal_status, type1, iteration, outbound_2h_avg, timestamp, method)
			payload += "mod_code,ip_address={0},start_beam={1},end_beam={2},status={3},type={4},method={8},iteration={5} value={6} {7}\n".format(ip_address, beam, end_beam, terminal_status, type1, iteration, mod_code, timestamp, method)
		
		payload += "initial_rl,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, initial_rl, timestamp, method)
		payload += "initial_fl,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, initial_fl, timestamp, method)
		payload += "predicted_rl,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, predicted_rl, timestamp, method)
		payload += "predicted_fl,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, predicted_fl, timestamp, method)
		payload += "actual_rl,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, actual_rl, timestamp, method)
		payload += "actual_fl,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, actual_fl, timestamp, method)
		payload += "outbound_terminal_count,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, len(terminal_list), timestamp, method)
		payload += "inbound_terminal_count,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, len(balance_data[beam]['terminals']), timestamp, method)
		payload += "hour,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, hour, timestamp, method)
		payload += "day,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, day, timestamp, method)
		payload += "month,beam={0},method={4},iteration={1} value={2} {3}\n".format(beam, iteration, month, timestamp, method)
		payload += "curr_method,iteration={0} value={1} {2}\n".format(method, iteration, timestamp)
		# payload += "bursts,beam={0},iteration={1} value={2} {3}\n".format(beam, iteration, bursts, timestamp)
		# payload += "burst_cap,beam={0},iteration={1} value={2} {3}\n".format(beam, iteration, burst_cap, timestamp)
		# payload += "congestion,beam={0},iteration={1} value={2} {3}\n".format(beam, iteration, congestion, timestamp)

	# logger.info(payload)
	return payload

def write_data():
	# logging.info(requests.get("http://192.168.220.37:8086/query?q=show+measurements&db=balance_data"))
	influxpost = requests.post("http://192.168.220.36:8086/write?db=balance_data&precision=s", data=get_payload())
	logging.info(influxpost)

if __name__ == '__main__':
	# get_payload()
	write_data()
