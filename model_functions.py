import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")
import copy

import json
from keras.models import load_model
from helper_functions import read_from_file
import numpy as np

import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logger = logging.getLogger('model_functions.log')
logger.setLevel(logging.INFO)

#RETURNS REGRESSION MODEL
def load_regression_model():
	return load_model('ml_model/models/linear_regression.h5')

#RETURNS PREDICTION FROM MODEL
def predict(model, feature_dic):
	feature_dic = copy.deepcopy(feature_dic)
	used_features = read_from_file('ml_model/res/used_features.txt')
	norm_metrics = json.load(open('ml_model/res/norm_metrics.json'))
	features = []
	for feature in used_features:

		if feature in norm_metrics:
			feature_dic[feature] = (feature_dic[feature] - norm_metrics[feature]['mean']) / norm_metrics[feature]['std']

		features.append(feature_dic[feature])

	return model.predict(np.array([features]))