from request_functions import request_terminal_status
from request_functions import request_beam_capacity
from case_driver import *
from helper_functions import write_json
from write_balance_data import write_data
from send_sftp import *
import json
import sys
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logger = logging.getLogger('balance_log')
logger.setLevel(logging.INFO)

timeout = 30

def goto_cases(driver):

	logger.info("redirecting to case page")
	driver.get('https://viasat.my.salesforce.com/home/home.jsp')

def comment_case(driver, case):
	try:
		element_present = EC.presence_of_element_located((By.ID, 'sbstr'))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. COMMENT_CASE() LOADING SEARCH BAR")
		driver.close()
		sys.exit()

	driver.find_element_by_id('sbstr').send_keys(case)
	driver.find_element_by_xpath("//*[@id='sbsearch']/div/div/input[2]").submit()


	try:
		element_present = EC.presence_of_element_located((By.XPATH, "//*[@id='Case_body']/table/tbody/tr[2]/td[2]/a"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. COMMENT_CASE() LOADING CASE")
		driver.close()
		sys.exit()

	driver.find_element_by_xpath("//*[@id='Case_body']/table/tbody/tr[2]/td[2]/a").click()

	try:
		element_present = EC.presence_of_element_located((By.XPATH, "//*[@id='bodyCell']/div[3]/div/div/div[1]/table/tbody/tr/td[2]/input"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. COMMENT_CASE() LOADING CASE")
		driver.close()
		sys.exit()

	driver.find_element_by_xpath("//*[@id='bodyCell']/div[3]/div/div/div[1]/table/tbody/tr/td[2]/input").click()

	try:
		element_present = EC.presence_of_element_located((By.XPATH, "//*[@id='ep']/div[2]/div[5]/table/tbody/tr/td[2]/div/textarea"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. COMMENT_CASE() CREATING COMMENT")
		driver.close()
		sys.exit()

	driver.find_element_by_xpath("//*[@id='ep']/div[2]/div[5]/table/tbody/tr/td[2]/div/textarea").send_keys("Please close this case even if not complete.")

	try:
		element_present = EC.presence_of_element_located((By.XPATH, "//*[@id='ep']/div[3]/table/tbody/tr/td[2]/input[1]"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. COMMENT_CASE() SUBMITTING COMENT")
		driver.close()
		sys.exit()

	driver.find_element_by_xpath("//*[@id='ep']/div[3]/table/tbody/tr/td[2]/input[1]").click()

def is_closed(driver, case):

	try:
		element_present = EC.presence_of_element_located((By.ID, 'sbstr'))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. IS_CLOSED() LOADING SEARCH BAR")
		driver.close()
		sys.exit()

	driver.find_element_by_id('sbstr').send_keys(case)
	driver.find_element_by_xpath("//*[@id='sbsearch']/div/div/input[2]").submit()


	try:
		element_present = EC.presence_of_element_located((By.XPATH, "//*[@id='Case_body']/table/tbody/tr[2]/td[4]"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. IS_CLOSED() LOADING CASE")
		driver.close()
		sys.exit()

	status = driver.find_element_by_xpath("//*[@id='Case_body']/table/tbody/tr[2]/td[4]").text
	logger.info(case)
	logger.info("Case status: {0}".format(status))

	if status == 'Closed':
		return True
	else:
		return False

def check_status(terminals):
	success = 0
	total = 0
	terminal_status = {}
	if len(terminals) > 0:
		results = request_terminal_status(terminals)
		for ip, curr_beam in results.items():
			total += 1
			expected_beam = terminals[ip][4]
			if expected_beam == curr_beam:
				success += 1
				terminal_status[ip] = 'pass'
				logger.info("SUCCESS {0} {1}".format(ip, curr_beam))

			else:
				terminal_status[ip] = 'fail'
				logger.info("FAIL {0} {1}".format(ip, curr_beam))

		logger.info("success rate: {0}/{1}".format(success, total))

	return terminal_status

def get_beam_info(beam_balance_data, case_info, case):
	#wAITS 10 MINUTES AFTER CASE IS CLOSED

	beam = case_info[case]['beam']
	terminal_status = check_status(case_info[case]['terminals'])
	logger.info(beam)
	logger.info("Requesting RL")
	actual_rl = request_beam_capacity(beam, 'RL', avg_time='5m')
	logger.info("Requesting FL")
	actual_fl = request_beam_capacity(beam, 'FL', avg_time='5m')

	beam_balance_data = json.load(open('res/beam_balance_data.json'))
	beam_balance_data[beam]['actual_rl'] = actual_rl
	beam_balance_data[beam]['actual_fl'] = actual_fl
	beam_balance_data[beam]['terminal_status'] = terminal_status
	
	return beam_balance_data

def get_all_beam_info(beam_balance_data, iterations):

	iterations['iterations'] += 1

	for beam in beam_balance_data:

		if 'terminal_status' not in beam_balance_data[beam]:
			terminals = get_terminal_list(beam_balance_data[beam])
			terminal_status = check_status(terminals)
			beam_balance_data[beam]['terminal_status'] = terminal_status

			logger.info(beam)
			logger.info("Requesting RL")
			actual_rl = request_beam_capacity(beam, 'RL')
			logger.info("Requesting FL")
			actual_fl = request_beam_capacity(beam, 'FL')

			beam_balance_data[beam]['actual_rl'] = actual_rl
			beam_balance_data[beam]['actual_fl'] = actual_fl

		beam_balance_data[beam]['iterations'] = iterations['iterations']


	allot_limits = json.load(open('config/allot_limits.json'))

	#PERCENTAGE DOES NOT REFLECT ALLOT BANDWIDTH
	for beam in allot_limits:
		if "RL" in allot_limits[beam]:
			beam_balance_data[beam]['actual_rl'] = (beam_balance_data[beam]['actual_rl']/allot_limits[beam]["RL"])*100
		if "FL" in allot_limits[beam]:
			beam_balance_data[beam]['actual_fl'] = (beam_balance_data[beam]['actual_fl']/allot_limits[beam]["FL"])*100

	write_json('res/iteration.json', iterations)
	write_json('data/balance_data.json', beam_balance_data)
	write_json('res/beam_balance_data.json', beam_balance_data)

	script_config = json.load(open('config/script_config.json'))

	if script_config['write_to_db']:
		logger.info('writting data.')
		write_data()
	else:
		logger.info('configured to skip writing data.')


def launch_balance_status_cases():
	curr_time = int(time.time())
	case_info = json.load(open('res/open_cases.json'))
	iterations = json.load(open('res/iteration.json'))
	beam_balance_data = json.load(open('res/beam_balance_data.json'))

	#LOGIN TO VIASAT
	driver = get_driver()

	login(driver)

	#CHECK FOR CLOSED CASES
	for case in case_info:

		#CHECK TERMINAL STATUS IF CLOSED AND 10 MINUTES HAS PASSED
		if case_info[case]['status'] == 'closed':
			if case_info[case]['check'] == False:
				if curr_time - case_info[case]['timestamp'] >= 599:
					beam_balance_data = get_beam_info(beam_balance_data, case_info, case)
					case_info[case]['check'] = True
				else:
					logger.info("{} curr time: {}".format(case, (curr_time - case_info[case]['timestamp'])))
		#IF NOT CLOSED CHECK IF IT HAS CLOSED
		else:
			goto_cases(driver)

			if is_closed(driver, case):
				case_info[case]['status'] = 'closed'
				case_info[case]['timestamp'] = curr_time

	write_json('res/beam_balance_data.json', beam_balance_data)
	write_json('res/open_cases.json', case_info)

	for case in case_info: 
		logger.info('case for: {} status: {}'.format(case_info[case]['beam'], case_info[case]['status']))

		#IF A CASE IS CLOSED BUT THE STATUS HASNT BEEN CHECKED WE WANT TO WAIT
		if case_info[case]['status'] == 'closed':
			if not case_info[case]['check']:
				logger.info('waiting for case to be checked')
				driver.close()
				sys.exit()

	#IF WE HAVE WAITED LONGER THAN 45 MINUTES COMMENT AND MOVE ON
	for case in case_info:
		if case_info[case]['status'] != 'closed':
			if curr_time - case_info[case]['timestamp'] < (60*45):
				logger.info("still waiting for cases to close.")
				driver.close()
				sys.exit()
			else:
				goto_cases(driver)
				comment_case(driver, case)

	driver.close()
	
	case_info = {}
	write_json('res/open_cases.json', case_info)

	#GET RL AND FL AND TERMINAL STATUS FOR THE REST OF THE BEAMS
	get_all_beam_info(beam_balance_data, iterations)
	sys.exit()

def launch_balance_status_sftp():

	#TIMESTAMP OF TIME BALANCE FILE WAS SENT TO SERVER
	sftp_time = json.load(open('res/sftp_time.json'))

	#IF 10 MINUTES HAS PASSED CHECK THE STATUS
	curr_time = int(time.time())
	if not sftp_time['processed']:

		# #CHECKS IF FILE HAS BEEN PROCESSED
		# processed_files = ls_sftp('processed/')
		# if sftp_time['filename'] in processed_files:
		# 	logger.info('csv file has been processed.')
		# 	sftp_time['processed'] = True
		# 	sftp_time['time_processed'] = curr_time
		# 	write_json('res/sftp_time.json', sftp_time)
		# else:
		# 	logger.info('csv file not yet processed.')
		# 	sys.exit()

		#CHECKS LOG FILE FOR PROCESS
		get_sftp()
		processor_log = open('logs/processor.log')
		for line in processor_log:
			if sftp_time['filename'] in line and "processed" in line:
				logger.info('csv file has been processed.')
				sftp_time['processed'] = True
				sftp_time['time_processed'] = curr_time
				write_json('res/sftp_time.json', sftp_time)
				break

		if not sftp_time['processed']:
			logger.warning('csv file not yet processed.')
			sys.exit()
			# #ONLY WAIT UP TO 25 MINUTES FOR FILE TO PROCESS
			# if curr_time - sftp_time['time_sent'] > (25*60)-15:
			# 	logger.info('max wait time exceeded')

			# 	if exists_sftp('uploads/{}'.format(sftp_time['filename'])):
			# 		logger.info('{} exists.'.format(sftp_time['filename']))
			# 		logger.info('removing file to perform new balance.')
			# 		rm_sftp('uploads/{}'.format(sftp_time['filename']))
			# 	else:
			# 		logger.info('{}} does not exist.'.format(sftp_time['filename']))

			# 	write_json('res/sftp_time.json', {})
			# 	logger.info('exiting')	
			# 	sys.exit()
			# else:
			# 	logger.info('waiting for {} to be processed.'.format(sftp_time['filename']))


	if (curr_time - sftp_time['time_processed']) >= (60*10)-15:
		sftp_time['time_checked'] = curr_time
		write_json('res/sftp_time.json', sftp_time)

		iterations = json.load(open('res/iteration.json'))
		beam_balance_data = json.load(open('res/beam_balance_data.json'))

		get_all_beam_info(beam_balance_data, iterations)
		
		write_json('res/sftp_time.json', {})

	else:
		logger.info('waiting to check balance status. {}'.format((int(time.time()) - sftp_time['time_processed'])))

	sys.exit()

def quick_check():
	case_info = json.load(open('res/open_cases.json'))

	for case in case_info:
		logger.info(case_info[case]['beam'])
		check_status(case_info[case]['terminals'])


if __name__ == "__main__":
	# launch_balance_status()
	quick_check()
