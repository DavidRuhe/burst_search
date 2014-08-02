#! /usr/bin/python
"""Program to monitor directory for new data and search for fast radio bursts
in GUPPI data.

Processes all data found in the search directory

"""

import time
import argparse
import glob
import multiprocessing
import threading
from os import path

import yaml
import watchdog.observers
import watchdog.events

# Command line arguments.
parser = argparse.ArgumentParser(description='Search GUPPI data for FRBs.')
parser.add_argument("parameter_file", metavar="parameter file", type=str,
                    help="YAML file with setup parameters.")
parser.add_argument(
    "--search-dir",
    nargs=1,
    help=("Directory containing data to be searched or for"
          " new data. Overrides the value provied in parameter file."),
    )
parser.add_argument(
        "--no-real-time",
        help="Do not do real-time search, just process pre-existing files.",
        action='store_true',
        )
parser.add_argument(
        "--no-pre-existing",
        help="Do not search pre-existing files, just do real-time search.",
        action='store_true',
        )


# Function that processes a file.
def process_file(filename, return_queue, **kwargs):
    print "start: %s" % filename
    time.sleep(2)
    return_code = 0
    return_queue.put((filename, return_code))


# Driver function for thread that processes pre-existing files.
def process_preexisting(file_pattern, ignore_files, return_queue, **kwargs):
    files_to_search = glob.glob(file_pattern)
    for filename in files_to_search:
        filename = path.abspath(filename)
        if filename in ignore_files:
            continue
        p = multiprocessing.Process(target=process_file,
                args=(filename, return_queue,), kwargs=kwargs)
        p.start()
        p.join()


# What to do with new files.
class NewFileHandler(watchdog.events.PatternMatchingEventHandler):
    
    def __init__(self, patterns=None, ignore_patterns=None,
                 ignore_directories=False, case_sensitive=False,
                 return_queue=None, **kwargs):
        watchdog.events.PatternMatchingEventHandler.__init__(
                self,
                patterns=patterns,
                ignore_patterns=ignore_patterns,
                ignore_directories=ignore_directories,
                case_sensitive=case_sensitive)

        self._return_queue = return_queue
        self._parameters = kwargs

    def on_created(self, event):
        if event.is_directory:
            return
        filename = event.src_path
        filename = path.abspath(filename)
        p = multiprocessing.Process(target=process_file,
                args=(filename, return_queue,), kwargs=self._parameters)
        p.start()
        p.join()


if __name__ == "__main__":
    args = parser.parse_args()

    # Read parameter file.
    with open(args.parameter_file) as f:
        parameters = yaml.safe_load(f.read())
    if args.search_dir:
        parameters["search_directory"] = args.search_dir
    parameters["search_directory"] = path.expanduser(parameters["search_directory"])
    file_pattern = path.join(parameters['search_directory'],
                             parameters['filename_match_pattern'])

    # Return codes go here.
    return_queue = multiprocessing.Queue()

    log_filename = path.join(path.expanduser(parameters["output_directory"]),
                             parameters['log_filename'])

    # Read the log file if it exists to see what has already been processed.
    if path.isfile(log_filename):
        with open(log_filename) as f:
            files_processed = yaml.safe_load(f.read())
    else:
        files_processed = {}

    # Setup a thread to process any files that already exist in the directory.
    if not args.no_pre_existing:
        pre_existing_thread = threading.Thread(target=process_preexisting,
                args=(file_pattern, files_processed.keys(), return_queue),
                kwargs=parameters)
    # Setup a watchdog thread to monitor for new files and process them as they
    # appear.
    if not args.no_real_time:
        event_handler = NewFileHandler(patterns=[file_pattern],
                                       case_sensitive=True, **parameters)
        # Set up and start new file monitor.
        observer = watchdog.observers.Observer()
        observer.schedule(event_handler, parameters['search_directory'],
                          recursive=False)

    with open(log_filename, 'a') as log_f:
        # Start threads.
        if not args.no_pre_existing:
            pre_existing_thread.start()
        if not args.no_real_time:
            observer.start()

        try:
            # Now enter holding loop until keyboard interrupt.
            while True:
                done_file, return_code = return_queue.get()
                log_f.write("%s: %d\n" % (done_file, return_code))
                # Don't wait for interrupt if not doing real-time search and all
                # work is done.
                no_work_left = args.no_real_time
                no_work_left = no_work_left and (args.no_pre_existing
                                        or not pre_existing_thread.is_alive())
                no_work_left = no_work_left and return_queue.empty
                if no_work_left:
                    break
        except KeyboardInterrupt:
            if not args.no_real_time:
                observer.stop()
                observer.join()
            if not args.no_pre_existing:
                pre_existing_thread.join()

