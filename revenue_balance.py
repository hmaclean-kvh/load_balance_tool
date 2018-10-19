import json
from config_info import get_database_config
from helper_functions import *
from request_functions import *

import logging

logger = logging.getLogger('load_balance_log')
logger.setLevel(logging.INFO)

INBOUND = "FL"
OUTBOUND = "RL"

#RETURNS LIST OF IPS TO BALANCE ARGS: CURRENT BEAM, DICT OF TERMINALS, CONTENTION TYPE RL OR FL
def get_payload(current_beam):

	# Construct Payload
	payload = {}
	payload["fields[]"] = ['beam', 'element_name', 'availability','outbound_last_15m_avg','inbound_last_15m_avg','beam_logoffs_sequence','beam_truly_connected','beam_destination_index', 'mod_code', 'outbound_last_2h_avg', 'inbound_last_2h_avg']
	payload["filters[beam_logoffs_sequence][from]"] = [current_beam]
	payload['filters[beam_logoffs_sequence][to]'] = ['ALL']
	payload['filters[availability][values]'] = ['online']
	payload["pagination[page]"] = ['1']
	payload["pagination[count]"] = ['200']
	payload['sorting[direction]']= ['asc']
	payload['sorting[name]']= ['outbound_last_15m_avg']

	return payload

#REQUESTS LIST OF IPS TO BALANCE ARGS: CURRENT BEAM NAME AND CONTENTION TYPE RL OR FL
def request_revenue_list(current_beam_config):

	payload = get_payload(current_beam_config)

	#INFO TO REQUEST TO DATABASE
	request_config, request_headers = get_database_config()

	#SEND REQUEST
	r = requests.Session()

	r = r.get(request_config['Rebalance'], headers=request_headers, params=payload)
	logger.info("{} request received.".format(current_beam_config))

	#PARSE REQUEST
	data =  r.json()['data']

	#CLOSE REQUEST SESSION
	r.close()

	logger.info("creating list of ip addresses to balance")
	
	return data

def launch_revenue_balance(current_beam_config):

	#DICTIONARY THAT MAPS BEAM NAMES TO DIFFERENT FORMATS
	beam_map = json.load(open('res/beam_map.json'))

	kvh_beams = read_from_file('res/kvh_beams.txt')
	ku_beams = read_from_file('res/ku_nms.txt')

	terminal_list = request_revenue_list(current_beam_config)

	print(current_beam_config)
	print(len(terminal_list))
	viasat = 0
	count = 0
	rl_total = 0

	redirects = {}
	logoffs = {}

	for terminal in terminal_list:
		ip_address = terminal['element_name']

		#EXCEPTION IF INDEX RETURNED IS NOT AN INTEGER EX: NONE
		try:
			beam_destination_index = int(terminal['beam_destination_index']) - 1
		except TypeError:
			# logger.critical("{0} NO DESTINATION BEAM INDEX".format(ip_address))
			continue

		#VARIABLES FOR CURRENT TERMINAL
		current_beam = terminal['beam']
		beam_logoffs_sequence = terminal['beam_logoffs_sequence'].split(",")
		inbound_last_15m_avg = float(terminal['inbound_last_15m_avg'])
		outbound_last_15m_avg = float(terminal['outbound_last_15m_avg'])
		mod_code = terminal['mod_code']
		inbound_last_2h_avg = float(terminal['inbound_last_2h_avg'])
		outbound_last_2h_avg = float(terminal['outbound_last_2h_avg'])

		#IF BEAM_TRULY_CONNECTED EQUALS 'VIASAT' THEN >1MB HAS BEEN USED ON VIASAT BEAMS 
		if terminal['beam_truly_connected'] is None:
			beam_truly_connected = []
		else:
			beam_truly_connected = terminal['beam_truly_connected'].split(",")

		#DESTINATION BEAM NAME
		destination_beam = beam_map['acu'][beam_logoffs_sequence[beam_destination_index]]

		#LIST CONTAINING THE BEAM CAPACITIES
		beam_sequence_bandwidth = {}

		# if outbound_last_15m_avg < 10:
	
		if 'KVH' not in beam_truly_connected and 'JSAT' not in beam_truly_connected:
				
			added = False
			for beam in beam_logoffs_sequence:

				next_beam = beam_map['acu'][beam]

				if next_beam != current_beam_config and next_beam in kvh_beams and next_beam in ku_beams:

					if next_beam != destination_beam:
						#CHECKS IF THE KEY FOR THE BEAM ALREADY EXISTS
						if next_beam in redirects:
							redirects[next_beam][ip_address] = [outbound_last_15m_avg, inbound_last_15m_avg, mod_code, 'redirect', next_beam, outbound_last_2h_avg, inbound_last_2h_avg]
						#IF NOT CREATE NEW ENTRY
						else:
							redirects[next_beam] = {ip_address: [outbound_last_15m_avg, inbound_last_15m_avg, mod_code, 'redirect',next_beam, outbound_last_2h_avg, inbound_last_2h_avg]}

					else:
						#ADD IP AND DATA TO LOGOFF LIST
						logoffs[ip_address] = [outbound_last_15m_avg, inbound_last_15m_avg, mod_code, 'logoff', next_beam, outbound_last_2h_avg, inbound_last_2h_avg]

					rl_total += outbound_last_15m_avg
					added = True
					count+=1
					break
			if not added:
				viasat+=1


	#SAVES LISTS TO FILE
	beam_balance_data[current_beam_config]['logoffs'] = logoffs
	beam_balance_data[current_beam_config]['redirects'] = redirects

	#SAVE NEW BEAM DATA
	write_json('res/beam_balance_data.json', beam_balance_data)

	print(viasat)
	print(count)
	print(rl_total)

if __name__ == '__main__':
	kvh_beams = read_from_file('res/kvh_beams.txt')
	beam_config = json.load(open('res/beam_config.json'))
	#CLEARS BEAM BALANCE DATA AND SETS TO 0
	init_beam_balance_cycle(beam_config.keys())

	#LOADS THE INITIALIZED DICTIONARY
	beam_balance_data = json.load(open('res/beam_balance_data.json'))

	#WRITE UPDATE STRUCTURES TO FILE
	write_json('res/beam_balance_data.json', beam_balance_data) 

	for beam in beam_config:

		if beam not in kvh_beams:
			launch_revenue_balance(beam)
