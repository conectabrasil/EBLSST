#!/software/anaconda3.6/bin/python

from EBLSST import LSSTEBworker, BreivikGalaxy
import multiprocessing, logging
import csv
import argparse
import numpy as np


def define_args(parser):
	parser.add_argument("-n", "--n_cores", 		type=int, help="Number of cores [0]")
	parser.add_argument("-c", "--n_bin", 		type=int, help="Number of binaries [100000]")
	parser.add_argument("-i", "--gal_file", 	type=str, help="Galaxy input file name")
	parser.add_argument("-o", "--output_file", 	type=str, help="output file name")
	parser.add_argument("-a", "--n_band", 		type=int, help="Nterms_band input for gatspy [2]")
	parser.add_argument("-b", "--n_base", 		type=int, help="Nterms_base input for gatspy [2]")
	parser.add_argument("-s", "--seed", 		type=int, help="random seed []")
	parser.add_argument("-p", "--plots", 		action='store_true', help="Set to create plots")
	parser.add_argument("-v", "--verbose", 		action='store_true', help="Set to show verbose output")
	parser.add_argument("-l", "--opsim", 		action='store_true', help="set to run LSST OpSim, else run nobs =")


def apply_args(worker):

	parser = argparse.ArgumentParser()
	define_args(parser)

	#https://docs.python.org/2/howto/argparse.html
	args = parser.parse_args()
	#to print out the options that were selected (probably some way to use this to quickly assign args)
	opts = vars(args)
	options = { k : opts[k] for k in opts if opts[k] != None }
	print(options)

	if (args.n_cores is not None):
		worker.n_cores = args.n_cores
	if (worker.n_cores > 1):
		worker.do_parallel = True
	else:
		worker.n_cores = 1
		worker.do_parallel = False 

	if (args.n_bin is not None):
		worker.n_bin = args.n_bin

	if (args.gal_file is not None):
		worker.GalaxyFile = args.gal_file
		
	if (args.output_file is not None):
		worker.ofile = args.output_file

	if (args.n_band is not None):
		worker.n_band = args.n_band
	if (args.n_base is not None):
		worker.n_base = args.n_base

	worker.do_plot = args.plots
	worker.verbose = args.verbose
	worker.doOpSim = args.opsim

	#set the random seed
	if (args.seed is not None):
		worker.seed = args.seed





if __name__ == "__main__":

	manager = multiprocessing.Manager()
	#Our LSST EB class to use gatspy and ellc
	worker = LSSTEBworker()
	worker.initialize() #sets the random seed and reads in the filter files
	worker.return_dict = manager.dict()

	#Katie's code to generate the binaries
	g = BreivikGalaxy()

	#check for command-line arguments
	apply_args(worker)

	#define the correct paths to the input files and db
	worker.GalaxyFile ='../input/dat_ThinDisk_12_0_12_0.h5' #for Katie's model
	worker.dbFile = '../db/minion_1016_sqlite.db' #for the OpSim database	
	g.GalaxyFile ='../input/dat_ThinDisk_12_0_12_0.h5' #for Katie's model
	g.GalaxyFileLogPrefix ='../input/fixedPopLogCm_'

	#now get the binaries
	gxDat = g.LSSTsim()

	#get the summary cursor for OpSim, if necessary
	if (worker.doOpSim):
		print('Getting OpSim cursors...')
		worker.getCursors()


	#if we want logging
	#logger = multiprocessing.log_to_stderr()
	##logger.setLevel(logging.DEBUG)
	#logger.setLevel(multiprocessing.SUBDEBUG)

	#set up the output file
	csvfile = open(worker.ofile, 'wt')	
	worker.csvwriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)

	#write header
	worker.writeOutputLine(None, header=True)

	jobs = []
	j = 0
	for i, line in enumerate(gxDat):

		#define the binary parameters
		EB = worker.getEB(line, i)
		print(EB.AV, EB.Ared)
		EB.lineNum = i

		if (EB.observable):
			worker.return_dict[j] = EB
			p = multiprocessing.Process(target=worker.run_ellc_gatspy, args=(j,))
			jobs.append(p)
			j += 1
		else:
			worker.writeOutputLine(EB)


		if (len(jobs) == worker.n_cores or (i >= worker.n_bin and len(jobs) > 0)):
			#could print this to look at progress
			# print ('n_appmag_failure = ',  worker.n_appmag_failure)
			# print ('n_incl_failure = ', worker.n_incl_failure)
			# print ('n_period_failure = ', worker.n_period_failure)
			# print ('n_R_failure = ', worker.n_radius_failure)
			# print ('n_totalrun = ', worker.n_totalrun)

			#run the jobs
			if (worker.do_parallel):
				for k,job in enumerate(jobs):
					print("starting job ",k)
					x = job.start()
				for k,job in enumerate(jobs):
					print("joining job ",k)
					job.join()
			else:
				for k,job in enumerate(jobs):
					print("running job",k)
					job.run()

			#print the output
			for j in range(worker.n_cores):
				worker.writeOutputLine(worker.return_dict[j])
				csvfile.flush()
				if (worker.do_plot):
					if (worker.return_dict[j]['LSM'] != -999):
						 worker.make_gatspy_plots(j)


			 #raise Exception('stopping')
			jobs = []
			j = 0


	csvfile.close()


