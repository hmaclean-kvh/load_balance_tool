#!/usr/bin/env python3

def clear_dataset():
	#CLEARS ALL DATA FROM TRAINING SO A NEW DATASET CAN BE CREATED
	#STARTING FROM A DIFFERENT ITERATION
	
	open('res/iterations.txt', 'w').close()
	open('data/training_data.csv', 'w').close()

if __name__ == '__main__':
	clear_dataset()