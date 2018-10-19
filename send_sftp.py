import logging
logger = logging.getLogger('sftp_log')
logger.setLevel(logging.INFO)

import pysftp as sftp
from config_info import get_sftp_config
from helper_functions import write_json
import time
import datetime as dt
import sys

def create_connection():
	sftp_config = get_sftp_config()

	sftp_config['host']

	host = sftp_config['host']
	username = sftp_config['username']
	private_key = sftp_config['private_key']

	public_key = 'config/id_rsa_balance.pub'

	logger.info('connecting to {}'.format(host))

	try:
		cnopts = sftp.CnOpts()
		cnopts.hostkeys.load(public_key)
		connect = sftp.Connection(host=host, username=username, private_key=private_key, cnopts=cnopts)
	except Exception as e:
		logger.info(e)
		print(e)
		logger.warning('error in connecting over sftp.')
		logger.info('exiting. retry next balance.')
		sys.exit()

	return connect

def rm_sftp(filename):
	connect = create_connection()

	try:
		connect.remove(filename)
	except Exception as e:
		logger.info(e)
		print(e)
		logger.warning('error connecting over sftp')
		logger.info('exiting. retry next balance.')
		sys.exit()

	connect.close()

def exists_sftp(filename):
	connect = create_connection()

	try:
		return connect.exists(filename)
	except Exception as e:
		logger.info(e)
		print(e)
		logger.warning('error connecting over sftp')
		logger.info('exiting. retry next balance.')
		sys.exit()

	connect.close()

def ls_sftp(file):
	connect = create_connection()

	try:
		files = connect.listdir(file)
	except Exception as e:
		logger.info(e)
		print(e)
		logger.warning('error in ls sftp.')
		logger.info('exiting.')
		sys.exit()

	connect.close()
	logger.info('{} ls list received.'.format(file))

	return files

def get_sftp():

	connect = create_connection()

	remotepath = 'logs/processor.log'
	localpath = 'logs/processor.log'

	try:
		connect.get(remotepath=remotepath, localpath=localpath)
	except Exception as e:
		logger.info(e)
		print(e)
		logger.warning('error in getting file over sftp.')
		logger.info('exiting. retry next balance.')
		sys.exit()

	connect.close()
	logger.info('log file received.')
	#SAVE TIME SENT FOR CHECKING STATUS

def send_sftp():

	connect = create_connection()

	# date = dt.datetime.now()
	# date_str = "{}_{}_{}_{}_{}_balance.csv".format(date.hour, date.minute, date.day, date.month, date.year)
	time_sent = int(time.time())
	date_str = "balance_{}.csv".format(time_sent)

	localpath = 'res/balance.csv'
	remotepath = './uploads/{}'.format(date_str)

	try:
		connect.put(localpath, remotepath=remotepath)
	except Exception as e:
		logger.info(e)
		print(e)
		logger.warning('error in sending file over sftp.')
		logger.info('exiting. retry next balance.')
		sys.exit()

	connect.close()
	logger.info('file sent.')
	#SAVE TIME SENT FOR CHECKING STATUS
	sftp_time = {}
	sftp_time['time_sent'] = time_sent
	sftp_time['filename'] = date_str
	sftp_time['processed'] = False
	write_json('res/sftp_time.json', sftp_time)

if __name__ == '__main__':
	get_sftp()