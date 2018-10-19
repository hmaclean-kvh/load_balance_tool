from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from helper_functions import format_case_info
from helper_functions import write_json
from helper_functions import get_terminal_list
from config_info import get_login_config
from pprint import pprint
import time
import json
import sys
import logging

logger = logging.getLogger('case_driver')
logger.setLevel(logging.INFO)

timeout = 30

#init driver as global but don't open web page yet
def get_driver():
	options = Options()
	options.add_argument("--headless")
	driver = webdriver.Firefox(firefox_options=options)
	return driver

def login(driver):
	#GOTO WEBSITE
	logging.info("opening website.")
	try:
		driver.get('https://sso.viasat.com/federation/UI/Login')
	except:
		logger.warning("TIMEOUT LOADING LOGIN PAGE")
		driver.close()
		sys.exit()

	login_info = get_login_config()

	#LOGIN
	logging.info("entering login info")

	try:
		element_present = EC.presence_of_element_located((By.ID, "IDToken1"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. LOGIN(). LOADING PAGE")
		driver.close()
		sys.exit()

	driver.find_element_by_id("IDToken1").send_keys(login_info["username"])
	driver.find_element_by_id("IDToken2").send_keys(login_info["password"])
	driver.find_element_by_name("Login.Submit").submit()

	#WAITS UNTIL LOGGED IN
	try:
		element_present = EC.presence_of_element_located((By.CLASS_NAME, "via-app-header"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. LOGIN() LOGGING IN")
		driver.close()
		sys.exit()

def goto_search(driver):
		
	logger.info("redirecting to case page")

	#NEW CASE / SITE SEARCH
	driver.get('https://viasat--c.na5.visual.force.com/apex/ViaSite?id=00570000002MOQ5')

def search(driver, beam):
	
	try:
		element_present = EC.presence_of_element_located((By.ID, "genericSearch"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. SEARCH() SEARCH BAR")
		driver.close()
		sys.exit()

	logger.info("searching for beam")
	#ENTER BEAM IN SEARCH BAR
	driver.find_element_by_id("genericSearch").send_keys(beam)

	#CLICK SEARCH BUTTON
	driver.find_element_by_xpath('//*[@id="j_id0:searchform:searchcriteria:j_id36"]/input[1]').click()


	#CHECKBOX FIND ONE THAT SAYS HUB
	try:
		element_present = EC.presence_of_element_located((By.XPATH, '//*[@id="sites"]/tbody/tr/td[4]'))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. SEARCH() CHECK BOX")
		driver.close()
		sys.exit()

	getNext=True
	index = 0
	while(getNext):
		index+=1
		try:
			value = driver.find_element_by_xpath('//*[@id="sites"]/tbody/tr[{0}]/td[4]'.format(index)).text
			if value == "Hub":
				getNext = False
		except:
			logger.critical("COULD NOT FIND CORRECT BEAM FOR CASE. BEAM: {0}".format(beam))
			driver.close()
			sys.exit()


	#CHECKS THE BOX
	driver.find_element_by_xpath('//*[@id="sites"]/tbody/tr[{0}]/td[1]/input'.format(index)).click()

	#CLICKS CREATE CASE
	driver.find_element_by_xpath('//*[@id="j_id0:searchform:j_id50:j_id51:j_id52"]/input').click()

	try:
		element_present = EC.presence_of_element_located((By.XPATH, '//*[@id="j_id0:searchform:caseRecordType"]/option[2]'))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. SEARCH() SELECT DROP DOWN")
		driver.close()
		sys.exit()
	#SELECT DROP DOWN
	driver.find_element_by_xpath('//*[@id="j_id0:searchform:caseRecordType"]/option[2]').click()

def open_case(driver, beam, beam_info):

	title, description, terminal_count = format_case_info(beam, beam_info)
	pprint(title)
	pprint(description)

	#CONTINUE TO OPEN CASE
	driver.find_element_by_xpath('//*[@id="content"]/div[3]/input[2]').click()

	try:
		element_present = EC.presence_of_element_located((By.XPATH, "//*[@id='00N70000002k12t']/option[5]"))
		WebDriverWait(driver, timeout).until(element_present)
	except TimeoutException:
		logger.critical("WEBDRIVER TIMEOUT. OPEN CASE()")
		driver.close()
		sys.exit()

	#SELECT CATAGORY LOAD BALANCE
	driver.find_element_by_xpath("//*[@id='00N70000002k12t']/option[5]").click()
	#ENTER TOTAL TERMINAL COUNT
	driver.find_element_by_id('00N70000003K1Pj').send_keys(terminal_count)
	#ENTER SUBJECT LINE
	driver.find_element_by_id('cas14').send_keys(title)
	#ENTER DESCRIPTION
	driver.find_element_by_id('cas15').send_keys(description)
	#STORE CASE NUMBER
	return driver.find_element_by_xpath('//*[@id="ep"]/div[2]/div[3]/table/tbody/tr/td[2]').text

def submit_case(driver):
	driver.find_element_by_xpath("//*[@id='bottomButtonRow']/input[1]").click()

def launch_driver():

	#INIT DRIVER
	driver = get_driver()

	login(driver)

	#LOAD DATA FROM BALANCE
	beam_balance_data = json.load(open('res/beam_balance_data.json'))
	beam_map = json.load(open('res/beam_map.json'))

	#NEEDED FOR SEARCHING FOR CASE

	case_numbers = {}

	count = 0

	curr_time = int(time.time())

	for beam in beam_balance_data:
		count+=1

		#ONLY OPEN CASES FOR BEAMS WITH LOGOFFS OR REDIRECTS
		if beam_balance_data[beam]['logoffs'] or beam_balance_data[beam]['redirects']:
			
			goto_search(driver)
			logger.info(beam)
			search(driver, beam_map[beam]['viasat'])
			case = open_case(driver, beam, beam_balance_data[beam])
			logger.info(case)
			case_numbers[case] = {}
			case_numbers[case]['beam'] = beam
			case_numbers[case]['status'] = 'new'
			case_numbers[case]['timestamp'] = curr_time
			case_numbers[case]['check'] = False
			case_numbers[case]['terminals'] = get_terminal_list(beam_balance_data[beam]) 
			submit_case(driver)

	write_json('res/open_cases.json', case_numbers)


	driver.quit()
