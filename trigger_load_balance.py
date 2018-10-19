from load_balance import launch_load_balance
from helper_functions import *
from request_functions import *

logger = logging.getLogger('balance_log')
logger.setLevel(logging.INFO)

INBOUND = "FL"
OUTBOUND = "RL"

#RETURNS TRUE IF THE rl_trigger IS EXCEEDED
def beam_exceeds_limit(beam, current_percentage, trigger):

	#RETURN TRUE IF THE LIMIT IS EXCEEDED
	logger.info("current: {0} limit: {1}".format(current_percentage, trigger))
	if current_percentage > trigger:

		logger.info("limit exceeded.")
		return True
	else:

		logger.info("limit NOT exceeded")
		return False

#RETURNS LIST IF LOAD BALANCE IT TRIGGERED OTHERWISE EXIT
def trigger_load_balance(beam, rl_percentage, rl_trigger, fl_percentage, fl_trigger):

	#TRY TO PERFORM BALANCING IF THE LIMIT IS EXCEEDED
	logger.info("checking return link limit")
	rl_exceeds = beam_exceeds_limit(beam, rl_percentage, rl_trigger)
	logger.info("checking forward link limit")
	fl_exceeds = beam_exceeds_limit(beam, fl_percentage, fl_trigger)

	if rl_exceeds or fl_exceeds:
		logger.info("deciding to balance FL or  RL")
		#decides whether to balance by rl or fl if they both exceed limit
		if rl_exceeds and fl_exceeds:
			#ratio of percentage used to the limit the trigger is set to
			rl_ratio = rl_percentage/rl_trigger
			fl_ratio = rl_percentage/rl_trigger

			#PICKS THE GREATER RATIO
			if rl_ratio > fl_ratio:
				return launch_load_balance(beam, OUTBOUND)

			else:
				return launch_load_balance(beam, INBOUND)

		#IF ONLY RL EXCEEDS
		elif rl_exceeds:
			return launch_load_balance(beam, OUTBOUND)

		#ELSE ONLY FL EXCEEDS
		else:
			return launch_load_balance(beam, INBOUND)

	else:

		logger.info("exit")
		return False

def launch_trigger():

	#LOAD CONFIG INFO FROM JSON FILE
	beam_config = json.load(open('config/beam_config.json'))

	#CLEARS BEAM BALANCE DATA AND SETS TO 0
	init_beam_balance_cycle(beam_config.keys())

	#LOADS THE INITIALIZED DICTIONARY
	beam_balance_data = json.load(open('res/beam_balance_data.json'))

	#GETS INFO FROM THE TABLE HUBTOTALS2.PHP
	networktools_table = request_networktools_table()

	#EDITS THE RL BANDWIDTH BASED ON THE TABLE
	beam_config = set_rl_bandwidth(networktools_table, beam_config)

	#REQUESTS BALANCE DATA FROM DATABASE AND EDITS THE DICTIONARY
	beam_balance_data = set_percentages(beam_config, beam_balance_data, rl_var="rl_avg", fl_var="fl_avg")
	beam_balance_data = set_percentages(beam_config, beam_balance_data, avg_time='5m')

	allot_limits = json.load(open('config/allot_limits.json'))

	#PERCENTAGE DOES NOT REFLECT ALLOT BANDWIDTH
	for beam in allot_limits:
		if "RL" in allot_limits[beam]:
			beam_balance_data[beam]['rl_avg'] = (beam_balance_data[beam]['rl_avg']/allot_limits[beam]["RL"])*100
			beam_balance_data[beam]['RL'] = (beam_balance_data[beam]['RL']/allot_limits[beam]["RL"])*100
		if "FL" in allot_limits[beam]:
			beam_balance_data[beam]['fl_avg'] = (beam_balance_data[beam]['fl_avg']/allot_limits[beam]["FL"])*100
			beam_balance_data[beam]['FL'] = (beam_balance_data[beam]['FL']/allot_limits[beam]["FL"])*100

	#SAVES STARTING VALUES TO INITIAL
	for beam in beam_balance_data:
		beam_balance_data[beam]['initial_rl'] = beam_balance_data[beam][OUTBOUND]
		beam_balance_data[beam]['initial_fl'] = beam_balance_data[beam][INBOUND]

	#WRITE UPDATE STRUCTURES TO FILE
	write_json('res/beam_balance_data.json', beam_balance_data) 
	write_json('config/beam_config.json', beam_config)

	init_ml_feature_data(beam_balance_data)

	#WHETHER ANY TERMINALS HAVE MOVED
	balance_triggered = False

	#RUNS BALANCE ON EACH BEAM STARTING WITH THE LOWEST RL
	beam_list = sorted(beam_balance_data, key=lambda x:(beam_balance_data[x]['rl_avg'], x))
	allowed_beams = read_from_file('config/balance_list.txt')

	for beam in beam_list:

		if beam in allowed_beams: 

			logger.info("CURRENT BEAM: {0}".format(beam))

			#BEAM LIMIT FOR RL AND FL
			rl_trigger = beam_config[beam]['config']['rl_trigger']
			fl_trigger = beam_config[beam]['config']['fl_trigger']

			#FL AND RL CURRENT 30m AVG PERCENTAGES
			rl_percentage = beam_balance_data[beam]["rl_avg"]
			fl_percentage = beam_balance_data[beam]["fl_avg"]

			if trigger_load_balance(beam, rl_percentage, rl_trigger, fl_percentage, fl_trigger):
				balance_triggered = True

			#UPDATE BEAM DATA AFTER EACH ITERATION
			beam_balance_data = json.load(open('res/beam_balance_data.json'))
		else:
			logger.info("{} is on the block list".format(beam))
	logger.info("TRIGGER DONE.")

	#LOGS ALL BALANCE INFO SO IT IS MORE READABLE
	for beam in beam_balance_data:
	
		terminals = get_terminal_list(beam_balance_data[beam])
		if terminals:
			logger.info(beam)
			logger.info(beam_balance_data[beam]['initial_rl'])
			logger.info(beam_balance_data[beam]['RL'])
			for ip in terminals:
					logger.info("{} {} to {} rl: {} kbps fl: {} kbps".format(ip, terminals[ip][3],terminals[ip][4], terminals[ip][0], terminals[ip][1]))

	if balance_triggered:
		for beam in beam_balance_data:
			beam_balance_data[beam]['bursts'] = request_bursts(beam, '5m')
			beam_balance_data[beam]['burst_cap'] = request_burst_cap(beam, '5m')
			beam_balance_data[beam]['congestion'] = request_congestion(beam, '5m')

	write_json('res/beam_balance_data.json', beam_balance_data)

	return balance_triggered

#MAIN FUNCTION
if __name__ == "__main__":

	launch_trigger()