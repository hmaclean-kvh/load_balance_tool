import logging

import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")

import keras
from keras.models import Sequential, load_model
from keras.layers import Dense, Dropout, Activation, Flatten
import numpy as np
import pandas as pd
import math
import json
from copy import deepcopy
import sys

logger = logging.getLogger('ml_model.log')
logger.setLevel(logging.INFO)

learning_rate = 0.01
dropout_rate = 0.2

def write_json(filename, dictionary):
	file = open(filename, 'w')
	json_text = json.dumps(dictionary, sort_keys=True, indent=4)
	file.write(json_text)
	file.close()

#CONSTRUCT MODEL
def create_model():
	#creating model
	model = Sequential()
	model.add(Dense(2, input_shape=(35,), activation='linear', init='uniform'))
	model.add(Dense(1, activation='linear', init='uniform'))
	model.summary()

	#stochastic gradient descent optimizer
	adam = keras.optimizers.Adam(lr=learning_rate, beta_1=0.9, beta_2=0.999, epsilon=None, decay=0.0, amsgrad=False)
	# sgd = keras.optimizers.SGD(lr=0.00001, momentum=0.0, decay=0.0, nesterov=False)
	#using logcosh loss function
	#similar to mean squared error
	model.compile(loss='mse', optimizer=adam, metrics=['accuracy'])
	
	return model

#ONE HOT ENCODE FEATURE
def one_hot_encode(df, var):
	one_hot = pd.get_dummies(df[var])
	df = df.drop(var, axis=1)
	df = df.join(one_hot)
	return df

def calc_sin(x):
	return math.sin(x*(2*math.pi/24))

def calc_cos(x):
	return math.cos(x*(2*math.pi/24))

#CREATE DATAFRAME FROM CSV
def create_dataframe():
	df = pd.read_csv('data/training_data.csv')
	# np.random.seed(42)
	df = df.reindex(np.random.permutation(df.index))

	#ONE HOT ENCODE CATAGORICAL FEATURES
	df = one_hot_encode(df, 'beam')
	df = one_hot_encode(df, 'type')

	# df = cyclical_encode(df, 'hour')
	df['sin_hour'] = df['hour'].map(calc_sin)
	df['cos_hour'] = df['hour'].map(calc_cos)

	df = df.drop('hour', axis=1)

	return df

def unnormalize(df, norm_metrics):
	for feature in norm_metrics:
		df[feature] = (df[feature]*norm_metrics[feature]['std']) + norm_metrics[feature]['mean'] 
	return df

#DECIDE WHETHER NEW MODEL IS BETTER THAN CURRENT
def evaluate_new_model(new_model, x_test, y_test):

	temp_norm_metrics = json.load(open('res/temp_norm_metrics.json'))

	try:
		curr_model = load_model('models/linear_regression.h5')
		curr_norm_metrics = json.load(open('res/norm_metrics.json'))
	except:
		logger.info('file not found')
		logger.info('saving curr model')
		new_model.save('models/linear_regression.h5')
		write_json('res/norm_metrics.json', temp_norm_metrics)

		return 1

	new_score_test = new_model.evaluate(x_test, y_test, verbose=0)
	unnormalize(x_test, temp_norm_metrics)
	print(x_test[:1])

	normalize(x_test, curr_norm_metrics)
	curr_score_test = curr_model.evaluate(x_test, y_test, verbose=0)
	logger.info("new model mse: {}".format(new_score_test))
	logger.info("curr model mse: {}".format(curr_score_test))
	unnormalize(x_test, curr_norm_metrics)
	print(x_test[:1])

	if curr_score_test[0] > new_score_test[0]:
		logger.info('saving new model')
		new_model.save('models/linear_regression.h5')
		write_json('res/norm_metrics.json', temp_norm_metrics)
	else:
		logger.info('new model did not improve. keeping current model.')

#NORAMLIZE METRICS ARE MEAN AND STANDARD DEVIATION
def save_normalizers(features, train, filename):
	norm_metrics = {}

	for feature in features:
		norm_metrics[feature] = {}
		norm_metrics[feature]['mean'] = train[feature].mean()
		norm_metrics[feature]['std'] = train[feature].std()

	write_json(filename, norm_metrics)

	return norm_metrics

#NORMALIZE FEATURES TO Z SCORE
def normalize(df, norm_metrics):
	for feature in norm_metrics:
		df[feature] = (df[feature] - norm_metrics[feature]['mean']) / norm_metrics[feature]['std']
	return df

def write_features(filename, features):
	file = open(filename, 'w+')
	for feature in features:
		file.write("{}\n".format(feature))

def train_model():

	filename = 'models/temp_linear_regression.h5'

	model = create_model()

	df = create_dataframe()

	script_config = json.load(open('../config/script_config.json'))
	df = df.query('iteration >= {}'.format(script_config['ml_iteration']))

	#DROP DATA THAT DOESN'T CONTAIN A BALANCE
	df = df.query('inbound_count != 0  or outbound_count !=0')

	#list to normalize
	norm_f = ['removed_bandwidth', 'added_bandwidth', 'start_congestion', 'sin_hour', 'cos_hour', 'inbound_count', 'outbound_count']

	#list to drop
	drop = ['predicted_congestion', 'iteration']

	#value we are trying to predict
	y_data = df['end_congestion']

	df_norm = df

	#train and test features
	x_train = df_norm.sample(frac=0.8)
	x_test = df_norm.drop(x_train.index)


	#train and test labels
	y_train = x_train.pop("end_congestion")
	y_test = x_test.pop("end_congestion")

	my_predict = x_test['predicted_congestion']
	naive_predict = deepcopy(x_test['start_congestion'])

	write_features('res/all_features.txt', x_train.keys())

	#GETS VALUES FOR NORMALIZATION AND SAVES DATA TO FILE
	norm_metrics = save_normalizers(norm_f, x_train, 'res/temp_norm_metrics.json')

	#NORMALIZE FEATURES
	print(x_train[:1])
	x_train = normalize(x_train, norm_metrics)
	x_test = normalize(x_test, norm_metrics)

	for feature in drop:
		x_train = x_train.drop(feature, axis=1)
		x_test = x_test.drop(feature, axis=1)

	write_features('res/used_features.txt', x_train.keys())

	#CHECKPOINTS
	earlystop = keras.callbacks.EarlyStopping(monitor='val_loss', min_delta=0, patience=10, verbose=1, mode='auto', baseline=None)
	checkpoint = keras.callbacks.ModelCheckpoint(filename, monitor='val_loss', verbose=1, save_best_only=True, save_weights_only=False, mode='auto', period=1)
	training_logger = keras.callbacks.CSVLogger('logs/ml_model.log', separator=" ", append=True)

	#TRAIN
	model.fit(x_train, y_train, epochs=1000, batch_size=5, validation_data=(x_test, y_test), verbose=1, callbacks=[earlystop, checkpoint, training_logger])

	# evaluate_new_model(model)
	new_model = load_model(filename)

	new_score_train = new_model.evaluate(x_train, y_train, verbose=0)
	logger.info("new model training: {}".format(new_score_train))

	evaluate_new_model(new_model, x_test, y_test)

	total=0
	count=0

	for x, y in zip(naive_predict, y_test):
		count+=1
		total+=pow(x-y,2)
	logger.info("naive prediction mse: {}".format(total/count))

	total = 0
	count = 0
	for x, y in zip(my_predict, y_test):
		count+=1
		total+=pow(x-y,2)
	logger.info("calculation mse: {}".format(total/count))

if __name__ == '__main__':
	train_model()
