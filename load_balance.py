import json
from config_info import get_database_config
from helper_functions import *
from request_functions import request_terminal_list
from request_functions import request_balance_history
from model_functions import *

import logging

logger = logging.getLogger('load_balance_log')
logger.setLevel(logging.INFO)

INBOUND = "FL"
OUTBOUND = "RL"

#RETURNS LIST OF IPS TO BALANCE ARGS: CURRENT BEAM, DICT OF TERMINALS, CONTENTION TYPE RL OR FL
def launch_load_balance(current_beam_config, contention_type):

	script_config = json.load(open('config/script_config.json'))

	#BEAM CONFIGURATION PREDEFINED
	beam_config = json.load(open('config/beam_config.json'))

	#DICTIONARY THAT MAPS BEAM NAMES TO DIFFERENT FORMATS
	beam_map = json.load(open('res/beam_map.json'))

	#LOADS STORED DATA ON HOW MUCH LOAD HAS BEEN MOVED
	beam_balance_data = json.load(open('res/beam_balance_data.json'))

	feature_data = json.load(open('res/feature_data.json'))

	#MOD CODE CONVERTION RATES
	mod_code_constant = json.load(open('res/mod_code_constants.json'))

	#BEAM NAMES
	ku_beams = read_from_file('res/ku_beams.txt')
	kvh_beams = read_from_file('res/kvh_beams.txt')

	terminal_list = request_terminal_list(current_beam_config, contention_type)

	balance_history = request_balance_history()

	model = load_regression_model()

	#LIST OF IP ADDRESSES TO LOGOFF
	logoffs = {}

	#DICT FOR REDIRECTS TO EACH BEAM
	redirects = {}

	#COUNT OF HOW MANY TERMINALS ARE BEING MOVED
	terminal_count = 0

	#TOTAL INBOUND AND OUTBOUND USAGE
	inbound_link_usage = 0
	outbound_link_usage = 0
	bandwidth_percentage = 0

	#DATA FROM BEAM CONFIGS
	fl_bandwidth = float(beam_config[current_beam_config]["config"]["fl_bandwidth"])
	rl_bandwidth = float(beam_config[current_beam_config]["config"]["rl_bandwidth"])

	#SORTS LIST BASED ON BANDWIDTH PERCENTAGE
	if contention_type == INBOUND:
		terminal_list = sorted(terminal_list, key=lambda terminal: (float(terminal['inbound_last_15m_avg'])/(mod_code_constant[terminal['mod_code']]*fl_bandwidth)), reverse=True)

	elif contention_type == OUTBOUND: 
		#OUTBOUND AKA RL IS IN KBPS AND IS ALREADY SORTED THIS WAY
		pass

	else: 
		logger.warning("invalid contention type")

	for terminal in terminal_list:

		ip_address = terminal['element_name']

		#EXCEPTION IF INDEX RETURNED IS NOT AN INTEGER EX: NONE
		try:
			beam_destination_index = int(terminal['beam_destination_index']) - 1
		except TypeError:
			logger.critical("{0} NO DESTINATION BEAM INDEX".format(ip_address))

		#VARIABLES FOR CURRENT TERMINAL
		current_beam = terminal['beam']
		beam_logoffs_sequence = terminal['beam_logoffs_sequence'].split(",")
		inbound_last_15m_avg = float(terminal['inbound_last_15m_avg'])
		outbound_last_15m_avg = float(terminal['outbound_last_15m_avg'])
		mod_code = terminal['mod_code']
		inbound_last_2h_avg = float(terminal['inbound_last_2h_avg'])
		outbound_last_2h_avg = float(terminal['outbound_last_2h_avg'])

		#IF BEAM_TRULY_CONNECTED EQUALS 'VIASAT' THEN >1MB HAS BEEN USED ON VIASAT BEAMS 
		beam_truly_connected = terminal['beam_truly_connected']

		#DESTINATION BEAM NAME
		destination_beam = beam_map['acu'][beam_logoffs_sequence[beam_destination_index]]

		#START_BEAM IS FIRST IN SEQUENCE
		start_beam = beam_logoffs_sequence[0]

		#LIST CONTAINING THE BEAM CAPACITIES
		beam_sequence_bandwidth = {}

		block_list = read_from_file('config/block_list.txt')


		balance_ip = True


		#SKIP IP IF BALANCED TO MUCH IN 24HRS
		if ip_address in balance_history:

			if balance_history[ip_address] >= 5:
				balance_ip = False


		#SKIPS BEAMS THAT CAN ONLY GO TO CURR BEAM
		if len(beam_logoffs_sequence) > 1 and balance_ip:

			#CREATE DICTIONARY OF BEAM TO CAPACITY 
			#logoff_sequence beams are in acu format so it is converted to nms
			for beam in beam_logoffs_sequence:

				#SKIP IF CURRENT BEAM OR C-CAND
				if beam != current_beam and beam in ku_beams:
					beam_sequence_bandwidth[beam_map['acu'][beam]] = beam_balance_data[beam_map['acu'][beam]][contention_type]

			#SORTED LIST EACH ITEM IS (BEAM, CAPACITY)
			beam_sequence_bandwidth = sorted(beam_sequence_bandwidth.items(), key=lambda info: info[1])

			#CHECK EACH BEAM IN THE SEQUENCE LIST STARTING WITH THE LOWEST CONTENTION
			for next_beam, beam_usage in beam_sequence_bandwidth:

				if next_beam not in block_list:

					current_beam_rl_load = 0
					current_beam_fl_load = 0
					next_beam_rl_load = 0
					next_beam_fl_load = 0

					curr_beam_rl_features = []
					curr_beam_fl_features = []
					next_beam_rl_features = []
					next_beam_fl_features = []

					#USER ML MODEL OR NORMAL CALCULATION
					curr_beam_rl_features = feature_data[current_beam_config]["RL"].copy()
					curr_beam_fl_features = feature_data[current_beam_config]["FL"].copy()
					next_beam_rl_features = feature_data[current_beam_config]["RL"].copy()
					next_beam_fl_features = feature_data[current_beam_config]["FL"].copy()

					curr_beam_rl_features["removed_bandwidth"] += outbound_last_15m_avg
					curr_beam_rl_features['outbound_count'] += 1

					curr_beam_fl_features["removed_bandwidth"] += inbound_last_15m_avg
					curr_beam_fl_features['outbound_count'] += 1

					next_beam_rl_features["added_bandwidth"] += outbound_last_15m_avg
					next_beam_rl_features['inbound_count'] += 1

					next_beam_fl_features["added_bandwidth"] += inbound_last_15m_avg
					next_beam_fl_features['inbound_count'] += 1

					ml_current_beam_rl_load = float(predict(model, curr_beam_rl_features)[0][0])
					ml_current_beam_fl_load = float(predict(model, curr_beam_fl_features)[0][0])
					ml_next_beam_rl_load = float(predict(model, next_beam_rl_features)[0][0])
					ml_next_beam_fl_load = float(predict(model, next_beam_fl_features)[0][0])

					calc_current_beam_rl_load = beam_balance_data[current_beam_config][OUTBOUND] - ((outbound_last_15m_avg/rl_bandwidth) * 100)
					calc_current_beam_fl_load = beam_balance_data[current_beam_config][INBOUND] - ((inbound_last_15m_avg/(mod_code_constant[mod_code] * fl_bandwidth)) * 100)
					calc_next_beam_rl_load = ((outbound_last_15m_avg/(beam_config[next_beam]['config']['rl_bandwidth'])) * 100) + beam_balance_data[next_beam][OUTBOUND]
					calc_next_beam_fl_load = ((inbound_last_15m_avg/(mod_code_constant[mod_code]*beam_config[next_beam]["config"]["fl_bandwidth"])) * 100) + beam_balance_data[next_beam][INBOUND]

					if script_config['ml_model']:
						current_beam_rl_load = ml_current_beam_rl_load
						current_beam_fl_load = ml_current_beam_fl_load
						next_beam_rl_load = ml_next_beam_rl_load
						next_beam_fl_load = ml_next_beam_fl_load
					else:
						current_beam_rl_load = calc_current_beam_rl_load
						current_beam_fl_load = calc_current_beam_fl_load
						next_beam_rl_load = calc_next_beam_rl_load
						next_beam_fl_load = calc_next_beam_fl_load

					#CHECKS THAT THE LIMIT WON'T BE EXCEEDED AND THE NEXT BEAM IS LESS CONTENDED
					if (next_beam_rl_load < beam_config[next_beam]['config']['limit'] and 
						next_beam_fl_load < beam_config[next_beam]['config']['limit'] and 
						beam_balance_data[next_beam][OUTBOUND] < beam_balance_data[current_beam_config][contention_type] and 
						beam_balance_data[next_beam][INBOUND] < beam_balance_data[current_beam_config][contention_type]):

						beam_balance_data[next_beam]['terminals'].append(ip_address)

						beam_balance_data[next_beam][INBOUND] = next_beam_fl_load
						beam_balance_data[next_beam][OUTBOUND] = next_beam_rl_load
						beam_balance_data[current_beam_config][INBOUND] = current_beam_fl_load
						beam_balance_data[current_beam_config][OUTBOUND] = current_beam_rl_load
						beam_balance_data[next_beam]["ml_fl_prediction"] = ml_next_beam_fl_load
						beam_balance_data[next_beam]["ml_rl_prediction"] = ml_next_beam_rl_load
						beam_balance_data[current_beam_config]["ml_fl_prediction"] = ml_current_beam_fl_load
						beam_balance_data[current_beam_config]["ml_rl_prediction"] = ml_current_beam_rl_load
						beam_balance_data[next_beam]["calc_fl_prediction"] = calc_next_beam_fl_load
						beam_balance_data[next_beam]["calc_rl_prediction"] = calc_next_beam_rl_load
						beam_balance_data[current_beam_config]["calc_fl_prediction"] = calc_current_beam_fl_load
						beam_balance_data[current_beam_config]["calc_rl_prediction"] = calc_current_beam_rl_load

						feature_data[current_beam_config]['RL'] = curr_beam_rl_features
						feature_data[current_beam_config]['FL'] = curr_beam_fl_features
						feature_data[next_beam]['RL'] = next_beam_rl_features
						feature_data[next_beam]['FL'] = next_beam_fl_features

						#IF THE NEXT BEAM TO GO TO IS NOT NEXT IN SEQUENCE WE MUST DO A REDIRECT
						if next_beam != destination_beam:

							logger.info("{0} redirected to {1}".format(ip_address, next_beam))

							#CHECKS IF THE KEY FOR THE BEAM ALREADY EXISTS
							if next_beam in redirects:
								redirects[next_beam][ip_address] = [outbound_last_15m_avg, inbound_last_15m_avg, mod_code, 'redirect', next_beam, outbound_last_2h_avg, inbound_last_2h_avg]
							#IF NOT CREATE NEW ENTRY
							else:
								redirects[next_beam] = {ip_address: [outbound_last_15m_avg, inbound_last_15m_avg, mod_code, 'redirect',next_beam, outbound_last_2h_avg, inbound_last_2h_avg]}

							break

						else:

							logger.info("{0} logoff to {1}".format(ip_address, next_beam))

							#ADD IP AND DATA TO LOGOFF LIST
							logoffs[ip_address] = [outbound_last_15m_avg, inbound_last_15m_avg, mod_code, 'logoff', next_beam, outbound_last_2h_avg, inbound_last_2h_avg]

							break


					else:
						if (next_beam_rl_load + beam_balance_data[next_beam][OUTBOUND]) >= beam_config[next_beam]['config']['limit']:
							logger.info("{0} skipped. {1} rl will exceed limit {2}".format(ip_address, next_beam, beam_config[next_beam]['config']['limit']))
						elif (next_beam_fl_load + beam_balance_data[next_beam][INBOUND]) >= beam_config[next_beam]['config']['limit']:
							logger.info("{0} skipped. {1} fl will exceed limit {2}".format(ip_address, next_beam, beam_config[next_beam]['config']['limit']))
						elif beam_balance_data[next_beam][OUTBOUND] >= beam_balance_data[current_beam_config][contention_type]:
							logger.info("{0} skipped. {3} rl exceeds current beam {1} {2}".format(ip_address, beam_balance_data[next_beam][OUTBOUND], beam_balance_data[current_beam_config][contention_type], next_beam))	
						elif beam_balance_data[next_beam][INBOUND] >= beam_balance_data[current_beam_config][contention_type]:
							logger.info("{0} skipped. {3} fl exceeds current beam {1} {2}".format(ip_address, beam_balance_data[next_beam][INBOUND], beam_balance_data[current_beam_config][contention_type], next_beam))

		else:
			if len(beam_logoffs_sequence) <= 1:
				logger.info("{} skipped. only 1 beam in sequence".format(ip_address))

			if ip_address in balance_history:
				if balance_history[ip_address] >= 5:
					logger.info("{} balance_history: {}".format(ip_address, balance_history[ip_address]))

	if contention_type == "RL":
		if (beam_balance_data[current_beam_config]['initial_rl'] - beam_balance_data[current_beam_config]['RL']) < 2:
			logger.info('not enough bandwidth moved to balance')
			logger.info(beam_balance_data[current_beam_config]['initial_rl'])
			logger.info(beam_balance_data[current_beam_config]['RL'])
			return False
	elif contention_type == "FL":
		if (beam_balance_data[current_beam_config]['initial_fl'] - beam_balance_data[current_beam_config]['FL']) < 2:
			logger.info('not enough bandwidth moved to balance')
			logger.info(beam_balance_data[current_beam_config]['initial_fl'])
			logger.info(beam_balance_data[current_beam_config]['FL'])
			return False

	#SAVES LISTS TO FILE
	beam_balance_data[current_beam_config]['logoffs'] = logoffs
	beam_balance_data[current_beam_config]['redirects'] = redirects

	#SAVE NEW BEAM DATA
	write_json('res/beam_balance_data.json', beam_balance_data) 
	write_json('res/feature_data.json', feature_data) 

	if len(logoffs) > 0 or redirects: 
		return True
	else:
		return False
