#!/usr/bin/env python3
import logging
logging.basicConfig(filename='logs/ml_model.log', format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

import json
import requests
from update_model import train_model

def get_iterations():
	iterations = []
	r = requests.get("http://192.168.220.36:8086/query?q=SHOW+TAG+VALUES+FROM+actual_fl+WITH+KEY+%3D+iteration&db=balance_data").json()
	for element in r['results'][0]['series'][0]['values']:
		iterations.append(element[1])
	return iterations

def request_feature(feature, iteration, tag_name, action = ""):
	r = requests.get("http://192.168.220.36:8086/query?q=select+{3}(value)+from+{0}+where+iteration+%3D+'{1}'++group+by+{2}&db=balance_data".format(feature, iteration, tag_name, action)).json()['results'][0]
	logging.info("request received. {}".format(feature))
	feature={}
	if len(r) > 1:
		for element in r['series']:
			feature[element['tags'][tag_name]] = element['values'][0][1]
	return feature

def get_info(beam, dic):
	if beam in dic:
		return dic[beam]
	else:
		return 0

def read_from_file(filename):
	file = open(filename, 'r')
	return file.read().splitlines()

def main():

	csv_data = ""

	iterations = get_iterations()

	prev_iterations = read_from_file('res/iterations.txt')

	if len(prev_iterations) == 0:
		csv_data = "iteration,beam,type,hour,removed_bandwidth,added_bandwidth,start_congestion,inbound_count,outbound_count,predicted_congestion,end_congestion\n"
	count = 0

	for iteration in iterations:

		if iteration != 'TEST':

			if iteration not in prev_iterations:
				count+= 1
				logging.info(iteration)
				prev_iterations.append(iteration)

				#ALL FEATURES
				start_rl_sums = request_feature("outbound_15m_avg", iteration, 'start_beam', "sum")
				end_rl_sums = request_feature("outbound_15m_avg", iteration, 'end_beam', "sum")
				start_fl_sums = request_feature("inbound_15m_avg", iteration, 'start_beam', "sum")
				end_fl_sums = request_feature("inbound_15m_avg", iteration, 'end_beam', "sum")
				actual_fls = request_feature("actual_fl", iteration, 'beam')
				actual_rls = request_feature("actual_rl", iteration, 'beam')
				initial_fls = request_feature("initial_fl", iteration, 'beam')
				initial_rls = request_feature("initial_rl", iteration, 'beam')
				predicted_fls = request_feature("predicted_fl", iteration, 'beam')
				predicted_rls = request_feature("predicted_rl", iteration, 'beam')
				inbound_terminal_counts = request_feature("inbound_terminal_count", iteration, 'beam')
				outbound_terminal_counts = request_feature("outbound_terminal_count", iteration, 'beam')
				hour = request_feature("hour", iteration, 'beam')

				for beam in actual_rls:
					csv_data += "{},{},{},{},{},{},{},{},{},{},{}\n".format(iteration, beam, "RL", get_info(beam, hour), get_info(beam, start_rl_sums), get_info(beam, end_rl_sums), get_info(beam, initial_rls), get_info(beam, inbound_terminal_counts), get_info(beam, outbound_terminal_counts), get_info(beam, predicted_rls), get_info(beam, actual_rls))
					csv_data += "{},{},{},{},{},{},{},{},{},{},{}\n".format(iteration, beam, "FL", get_info(beam, hour), get_info(beam, start_fl_sums), get_info(beam, end_fl_sums), get_info(beam, initial_fls), get_info(beam, inbound_terminal_counts), get_info(beam, outbound_terminal_counts), get_info(beam, predicted_fls), get_info(beam, actual_fls))	

	file = open('data/training_data.csv', 'a+')
	file.write(csv_data)
	file.close()

	file = open('res/iterations.txt', 'w+')

	for iteration in prev_iterations:
		file.write('{}\n'.format(iteration))

	file.close()

	train_model()

if __name__ == '__main__':
	main()
