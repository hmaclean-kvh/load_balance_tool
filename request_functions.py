import requests
from lxml import html
from bs4 import BeautifulSoup
from influxdb import InfluxDBClient
from config_info import get_database_config

import logging

logger = logging.getLogger('requests_log')
logger.setLevel(logging.INFO)

INBOUND = "FL"
OUTBOUND = "RL"

#GETS A BEAMS CURRENT PERCENTAGE USAGE FOR EITHER FL OR RL
def request_beam_capacity(beam, contention_type, avg_time='30m'):

	#CONNECT TO DATABASE
	db_client = InfluxDBClient(host='192.168.220.37', database='NEW_AVRO')

	#REQUEST FOR BEAM RETURN LINK USAGE %
	if contention_type == OUTBOUND:
		rl_results = db_client.query("SELECT mean(value) FROM rlCapacityPercent WHERE time > now()-{1} AND Beam = '{0}'".format(beam, avg_time))
		try:
			return float(rl_results.raw['series'][0]['values'][0][1])
		except:
			return 50.0
	#REQUEST FOR BEAM FORWARD LINK USAGE %
	elif contention_type == INBOUND:
		fl_results = db_client.query("SELECT sum(value) FROM outputFlPercentageNoPadding WHERE (Beam = '{0}' AND qosClass != '\"Available Bandwidth\"') AND time > now() - {1} GROUP BY time(30s) fill(none)".format(beam, avg_time))
		count = 0
		total = 0
		try:
			for entry in fl_results.raw['series'][0]['values']:
				total += entry[1]
				count += 1

			return total/count
		except:
			return 50.0
	else:
		logger.critical("NO CONTENTION TYPE SPECIFIED")

#AVERAGE BURST COUNT
def request_bursts(beam, avg_time='30m'):

	#CONNECT TO DATABASE
	db_client = InfluxDBClient(host='192.168.220.37', database='NEW_AVRO')
	results = db_client.query("SELECT mean(value) FROM averageNormalizedBurstCount WHERE time > now() - {} AND Beam = '{}'".format(avg_time, beam))
	return float(results.raw['series'][0]['values'][0][1])

#AVERAGE BURST CAPACITY
def request_burst_cap(beam, avg_time='30m'):

	#CONNECT TO DATABASE
	db_client = InfluxDBClient(host='192.168.220.37', database='NEW_AVRO')
	results = db_client.query("SELECT mean(value) FROM averageAdjustedNormalizedCapacityBursts WHERE time > now() - {} AND Beam = '{}'".format(avg_time, beam))
	return float(results.raw['series'][0]['values'][0][1])

#AVERAGE CONGESTION
def request_congestion(beam, avg_time='30m'):

	#CONNECT TO DATABASE
	db_client = InfluxDBClient(host='192.168.220.37', database='NEW_AVRO')
	results = db_client.query("SELECT mean(value) FROM averageCongestionThreshold WHERE time > now() - {} AND Beam = '{}'".format(avg_time, beam))
	return float(results.raw['series'][0]['values'][0][1])

#CONSTRUCTS THE PAYLOAD FOR MY KVH
def get_payload(current_beam, contention_type):

	# Construct Payload
	payload = {}
	payload["fields[]"] = ['beam', 'element_name','outbound_last_15m_avg','inbound_last_15m_avg','beam_logoffs_sequence','beam_truly_connected','beam_destination_index', 'mod_code', 'outbound_last_2h_avg', 'inbound_last_2h_avg']
	payload["filters[beam_logoffs_sequence][from][]"] = [current_beam]
	payload['filters[beam_logoffs_sequence][to]'] = ['ALL']
	payload["pagination[page]"] = ['1']
	payload["pagination[count]"] = ['50']
	payload['sorting[direction]']= ['desc']

	#DECIDES HOW TO SORT RESULTS
	if contention_type == OUTBOUND:
	    payload['sorting[name]']= ['outbound_last_15m_avg']
	else: 
	    payload['sorting[name]']= ['inbound_last_15m_avg']

	return payload

#REQUESTS LIST OF IPS TO BALANCE ARGS: CURRENT BEAM NAME AND CONTENTION TYPE RL OR FL
def request_terminal_list(current_beam_config, contention_type):

	payload = get_payload(current_beam_config, contention_type)

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

#RETURNS A MAP OF IPS TO THE LAST BEAM THEY CONNECTED TO
def request_terminal_status(terminals):
	#CONNECT TO DATABASE
	db_client = InfluxDBClient(host='192.168.220.37', database='VMT_AVRO')
	list_text = ""
	for terminal in terminals:
		logger.info(terminal)
		if list_text == "":
		    list_text += "vmtId = '{0}'".format(terminal)
		else:
		    list_text += " OR vmtId = '{0}'".format(terminal)

	results = db_client.query("SELECT last(hubName) FROM Periodic WHERE ({0}) GROUP BY vmtId".format(list_text))
	logger.info("terminal status request received.")

	#GET LIST FROM THE RESULTS DICTIONARY
	list_results = results.raw['series']

	#DICTIONARY OF IP TO BEAM
	connected_beam = {}

	for result in list_results:
		connected_beam[result['tags']['vmtId']] = result['values'][0][1]


	return connected_beam

#PARSEES TABLE TO GET INFO ABOUT EACH BEAM.
# [KEY][16] = NAME OF BEAM
def request_networktools_table():
	r = requests.get("http://networktools.ops.kvh.com/QR/HubTotals2.php")
	logger.info("networktools request received.")
	soup= BeautifulSoup(r.content, "lxml")
	table = soup.find_all('table')[1]
	table_dic = {}
	count = 0
	for column in table.find_all('td'):
		# count = 0
		# columns = row.find_all('td')
		# for column in columns:
		value = int(count/18)
		if value in table_dic:
		    table_dic[value].append(column.get_text())
		else:
		    table_dic[value] = [column.get_text()]
		count += 1
	return table_dic

def request_balance_history():
	db_client = InfluxDBClient(host='192.168.220.36', database='balance_data')
	results = db_client.query("SELECT count(value) FROM inbound_15m_avg WHERE time > now() - 24h GROUP BY ip_address")
	balance_history = {}
	for entry in results.raw['series']:
		balance_history[entry['tags']['ip_address']] = entry['values'][0][1]
	return balance_history

def request_ml_avg_error():
	db_client = InfluxDBClient(host='192.168.220.36', database='balance_data')
	results = db_client.query("SELECT mean(value) FROM ml_rl_squared_error WHERE time > now() - 24h")

	return float(results.raw['series'][0]['values'][0][1])

def request_calc_avg_error():
	db_client = InfluxDBClient(host='192.168.220.36', database='balance_data')
	results = db_client.query("SELECT mean(value) FROM calc_rl_squared_error WHERE time > now() - 24h")

	return float(results.raw['series'][0]['values'][0][1])

