import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from config_info import get_email_config
from helper_functions import create_csv
from helper_functions import write_json
import time
import logging

logger = logging.getLogger('email_csv_log')
logger.setLevel(logging.INFO)

def send_email():

	#SAVE TIME SENT FOR CHECKING STATUS
	email_time = {}
	email_time['time_sent'] = int(time.time())
	write_json('res/email_time.json', email_time)

	#LOGIN / PASSWORD
	email_config = get_email_config()

	#CONSTRUCT EMAIL TO SEND
	msg = MIMEMultipart()
	msg['Subject'] = "Load Balancing"
	msg['From'] = email_config['username']
	msg['To'] = 'dboslee@kvh.com'

	logger.info("preparing email to {0}".format(msg['To']))

	#CREATE CSV FROM BALANCE DATA
	create_csv()

	#ADD CSV AS ATATCHMENT
	part = MIMEBase('application', "octet-stream")
	part.set_payload(open("res/balance.csv", "rb").read())
	part.add_header('Content-Disposition', 'attachment; filename="Load_Balance.csv"')

	msg.attach(part)

	#CONNECT TO SERVER AND SEND
	server = smtplib.SMTP('smtp-mail.outlook.com', 587)
	server.starttls()
	server.login(email_config['username'], email_config['password'])
	text = msg.as_string()
	server.sendmail(msg['From'], msg['To'], text)
	server.quit()
	logger.info("email sent.")

if __name__ == '__main__':

	send_email()