from request_functions import request_beam_capacity
from datetime import datetime
import json
import sys
import math

import logging

logger = logging.getLogger('config_log')
logger.setLevel(logging.INFO)

INBOUND = "FL"
OUTBOUND = "RL"

#HELPER TO WRITE A DICTIONARY TO JSON FILE
def write_json(filename, dictionary):
	logger.info("writing file {0}".format(filename))
	file = open(filename, 'w+')
	json_text = json.dumps(dictionary, sort_keys=True, indent=4)
	file.write(json_text)
	file.close()

#HELPER TO READ FILE INTO A LIST
def read_from_file(filename):
	file = open(filename)
	return file.read().splitlines()

#takes one entry from beam balance data terminal, destination beam
def get_terminal_list(beam_data):
	terminals = {}
	for terminal in beam_data['logoffs']:
		terminals[terminal] = beam_data['logoffs'][terminal]

	for beam in beam_data['redirects']:
		for terminal in beam_data['redirects'][beam]:
			terminals[terminal] = beam_data['redirects'][beam][terminal]

	return terminals

def create_csv():
	logger.info('creating csv.')
	beam_balance_data = json.load(open('res/beam_balance_data.json'))
	beam_map = json.load(open('res/beam_map.json'))
	ips = []
	csv_text = ""
	for beam in beam_balance_data:
		for terminal in beam_balance_data[beam]['logoffs']:
			if terminal in ips:
				logger.warning('duplicate ip found while creating csv. {} skipping')
			else:
				ips.append(terminal)
				csv_text += "Logoff,{0}\n".format(terminal)
		for end_beam in beam_balance_data[beam]['redirects']:
			for terminal in beam_balance_data[beam]['redirects'][end_beam]:
				if terminal in ips:
					logger.warning('duplicate ip. {} skipping')
				else:
					ips.append(terminal)
					csv_text += "Redirect,{0},{1}\n".format(terminal, beam_map[end_beam]['viasat'])

	file= open('res/balance.csv', 'w+')
	file.write(csv_text)

#INITIALIZE THE VALUES FOR BALANCE DATA
def init_beam_balance_cycle(beams):
	logger.info('initializing balance data.')
	beam_balance_data = {}

	for beam in beams:
		beam_balance_data[beam] = {OUTBOUND: 0, INBOUND: 0, 'initial_rl': 0, 'initial_fl': 0, 'rl_avg': 0, 'fl_avg': 0, 'logoffs': {}, 'redirects': {}, 'terminals': []}

	write_json('res/beam_balance_data.json', beam_balance_data)

#CALCULATES THE RL CAPACITY FOR EACH BEAM BASED ON THE NETWORK TOOLS
def set_rl_bandwidth(networktools_table, beam_config):
    #
	logger.info('setting rl capacity from networktools table.')
	for element in networktools_table.values():
		beam = element[16]
		#HANDLE CASES WHERE TABLE IS EMPTY
		if element[15] == "":
			rl_remain= 0
		else:
			rl_remain = int(element[15])
		if element[11] == "":
			rl_usage = 0
		else:
			rl_usage = int(element[11])

		rl_cap =  rl_usage+rl_remain

		beam_config[beam]['config']['rl_bandwidth'] = rl_cap

	return beam_config

#SETS ALL PERCENTAGES FOR BOTH RL AND FL LINK
def set_percentages(beam_config, beam_balance_data, rl_var=OUTBOUND, fl_var=INBOUND, avg_time='30m'):
	#INITIALIZED BEAM INFO AND RL FL DATA
	for beam in beam_config:

		logger.info("Setting current congestion for {0}".format(beam))

		#CURRENT PERCENTAGE OF RL USED
		beam_balance_data[beam][rl_var] = request_beam_capacity(beam, OUTBOUND, avg_time)
		beam_balance_data[beam][fl_var] = request_beam_capacity(beam, INBOUND, avg_time)

	return beam_balance_data

def format_case_info(beam, beam_info):
	logoffs = beam_info['logoffs']
	redirects = beam_info['redirects']
	beam_map = json.load(open('res/beam_map.json'))
	logoff_text = ""
	redirect_text = ""
	title = beam_map[beam]['viasat'] + " Load Balance "
	total = 0

	if len(logoffs) > 0:
		logoff_text +="Logoffs: \n\n"
		for ip in logoffs:
			total += 1
			logoff_text += ip + "\n"
	if redirects:
		redirect_text += "Redirects: \n\n"
		for beam2 in redirects:
			redirect_text += "redirect to " + beam_map[beam2]['viasat'] + "\n"
			for ip in redirects[beam2]:
				total += 1
				redirect_text += ip + "\n"
			redirect_text += "\n"

	description = ""
	if redirect_text == "":
		title += "({0}) Logoffs".format(total)
		description = logoff_text
	elif logoff_text == "":
		title += "({0}) Redirects".format(total)
		description = redirect_text
	else:
		title+= "({0}) Logoffs and Redirects".format(total)
		description = logoff_text + "\n" + redirect_text

	return title, description, total

#CREATES DICTIONARY FOR EACH POSSIBLE FEATURE IN THE MODEL
def construct_feature_dic():
	feat_dic = {}
	features = read_from_file('ml_model/res/all_features.txt')

	for feature in features:
		feat_dic[feature] = 0

	return feat_dic

def get_moved_bandwidth(beam_balance_data):
	bandwidth = {}

	for beam in beam_balance_data:

		terminals = get_terminal_list(beam_balance_data[beam])

		for terminal in terminals:

			if beam not in bandwidth:
				bandwidth[beam] = {}
				bandwidth[beam]['removed_rl'] = 0
				bandwidth[beam]['removed_fl'] = 0
				bandwidth[beam]['added_rl'] = 0
				bandwidth[beam]['added_fl'] = 0
				bandwidth[beam]['outbound_count'] = 0
				bandwidth[beam]['inbound_count'] = 0

			bandwidth[beam]['removed_rl'] += terminals[terminal][0]
			bandwidth[beam]['removed_fl'] += terminals[terminal][1]
			bandwidth[beam]['outbound_count'] += 1

			end_beam = terminals[terminal][4]

			if end_beam not in bandwidth:
				bandwidth[end_beam] = {}
				bandwidth[end_beam]['removed_rl'] = 0
				bandwidth[end_beam]['removed_fl'] = 0
				bandwidth[end_beam]['added_rl'] = 0
				bandwidth[end_beam]['added_fl'] = 0
				bandwidth[end_beam]['outbound_count'] = 0
				bandwidth[end_beam]['inbound_count'] = 0

			bandwidth[end_beam]['added_rl'] += terminals[terminal][0]
			bandwidth[end_beam]['added_fl'] += terminals[terminal][1]
			bandwidth[end_beam]['inbound_count'] += 1

	return bandwidth

def calc_sin(x):
	return math.sin(x*(2*math.pi/24))

def calc_cos(x):
	return math.cos(x*(2*math.pi/24))

def init_ml_feature_data(beam_balance_data):
	beam_config = json.load(open('config/beam_config.json'))
	feature_data = {}
	hour = datetime.now().timetuple()[3]
	sin_hour = calc_sin(hour)
	cos_hour = calc_cos(hour)
	for beam in beam_config:
		rl_feature = construct_feature_dic()
		fl_feature = construct_feature_dic()
		rl_feature[beam] = 1
		rl_feature["RL"] = 1
		rl_feature['start_congestion'] = beam_balance_data[beam]['initial_rl']
		rl_feature['cos_hour'] = cos_hour
		rl_feature['sin_hour'] = sin_hour
		fl_feature[beam] = 1
		fl_feature["FL"] = 1
		fl_feature['start_congestion'] = beam_balance_data[beam]['initial_fl']
		fl_feature['cos_hour'] = cos_hour
		fl_feature['sin_hour'] = sin_hour
		feature_data[beam] = {}
		feature_data[beam]["RL"] = rl_feature
		feature_data[beam]["FL"] = fl_feature

	write_json('res/feature_data.json', feature_data)