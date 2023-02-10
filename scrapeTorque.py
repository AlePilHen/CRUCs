"""
    Author: Alexander Henriksen
    Data: February 2023
    Description: This script was made to scrape a toque accounting file
                 to extract all information on use of CPUs, memory and time.
                 It then outputs this information into a .csv file, which can 
                 be used by the torqueDork.py script to calculate statistics.
    
    Input:
        1) A torque accounting file
    Output:
        1) A .csv file containing job information

    USAGE:
        python scrapeTorque.py <torque_logfile> 

    IDEAS:
        - Change output of scrapeTorque.py so that the output is 
          summary statistics and so that TorqueDork.py simply
          reads that summary and presents it.
"""

import pandas as pd
import datetime
import argparse
import sys 
import os
import re
import pdb

## ------------------- Functions ------------------- ##

def walltime_to_seconds(walltime):
    """
    This function takes a walltime in the format of the torque accounting file
    (DD:HH:MM:SS) and converts it to seconds.
    """

    # Split the walltime into days, hours, minutes and seconds
    walltime = walltime.split(":")
    if len(walltime) == 3:
        days = 0
        hours = int(walltime[0])
        minutes = int(walltime[1])
        seconds = int(walltime[2])
    elif len(walltime) == 4:
        days = int(walltime[0])
        hours = int(walltime[1])
        minutes = int(walltime[2])
        seconds = int(walltime[3])

    # Convert to seconds
    seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds

    return str(seconds)


def memory_to_mb(memory):
    """
    This function takes a memory request in the format of the torque accounting file
    (e.g. 10gb) and converts it to MB.
    """

    # In case no memory was requested, assume a full node
    if memory == "1":
        return str(180 * 1024)

    # Extract the memory amount and the unit
    memory_amount = int(memory[:-2])
    memory_unit = memory[-2:]

    # Convert to MB
    if memory_unit == "gb":
        memory = memory_amount * 1024
    elif memory_unit == "mb":
        memory = memory_amount
    elif memory_unit == "kb":
        memory = memory_amount / 1024

    return str(memory)

def get_line_match(pattern, string):
    """
    This function takes a string and a pattern and returns
    a regex match. If no match is found, it returns 0.
    """

    match = re.search(pattern, string)
    if match:
        return match.group(1)
    else:
        return "1"


def build_date_list(start_date, end_date):
    """
    This function takes two dates in the format of the torque accounting file
    and returns a list of dates in the same format.
    """
    # Convert the dates to datetime objects
    start_date = datetime.datetime.strptime(start_date, "%Y%m%d")
    end_date = datetime.datetime.strptime(end_date, "%Y%m%d")

    # Create a list of dates between the two dates
    date_list = []
    for date in pd.date_range(start_date, end_date):
        date_list.append(date.strftime("%Y%m%d"))

    return date_list


def extract_torque_data(date, output_file, torque_path, server_logs):
    """
    This function goes through a torque accounting file and extracts
    relevant information on resource use.
    """

    torque_file = os.path.join(torque_path, date)

    # Check if the file exists
    if not os.path.isfile(torque_file):
        print("File {} does not exist.".format(torque_file))
        return

    # Open the torque accounting file
    with open(torque_file, "r") as infile, open(output_file, "a") as outfile:

        # Go through the file line by line
        for line in infile:

            # Find lines with information on ended jobs
            if re.search("Exit_status=\d+", line):

                # extract line
                #line = line.strip("\n").split(" ")

                # Initialize dictionary
                data = {}

                # Define patterns to extract information
                if server_logs:
                    patterns = {"date":          "(^[0-9/]{10})",
                                "exit_status":   "Exit_status=(\d+)",
                                "used_walltime": "resources_used\.walltime=([0-9:]+)",
                                "used_mem":      "resources_used\.mem=(\d+\w+)",
                                "used_cput":     "resources_used\.cput=(\d+)"}

                else:
                    patterns = {"date":          "(^[0-9/]{10})",
                                "user":          "user=(\w+)",
                                "exit_status":   "Exit_status=(\d+)",
                                "req_walltime":  "Resource_List\.walltime=([0-9:]+)",
                                "req_mem":       "Resource_List\.mem=(\d+\w+)",
                                "req_nodes":     "Resource_List\.nodes=(\d+)",
                                "req_cpus":      "Resource_List.+ppn=(\d+)",
                                "req_gpus":      "Resource_List.+gpu=(\d+)",
                                "used_walltime": "resources_used\.walltime=([0-9:]+)",
                                "used_mem":      "resources_used\.mem=(\d+\w+)",
                                "used_cput":     "resources_used\.cput=(\d+)"}

                # Extract information
                for name in patterns.keys():
                    data[name] = get_line_match(patterns[name], line)
            
                if server_logs:
                    data["user"] = "server"
                    data["req_walltime"] = data["used_walltime"]
                    data["req_mem"] = data["used_mem"]
                    data["req_nodes"] = "1"
                    data["req_gpus"] = "0"

                # Format extracted data for output
                req_walltime = walltime_to_seconds(data["req_walltime"])
                used_walltime = walltime_to_seconds(data["used_walltime"])
                req_mem = memory_to_mb(data["req_mem"])
                used_mem = memory_to_mb(data["used_mem"])

                if server_logs:
                    data["req_cpus"] = str(round(int(data["used_cput"]) / int(used_walltime)+1))

                # Calculate required cputime
                req_cputime = str(int(req_walltime) * int(data["req_cpus"]) * int(data["req_nodes"]))

                # Write information to file
                outfile.write(",".join([data["date"], data["user"], data["exit_status"],
                                        data["req_gpus"], data["req_cpus"],
                                        req_walltime, used_walltime,
                                        req_mem, used_mem,
                                        req_cputime, data["used_cput"]]) + "\n")


def parse_args():
    """
    Argument parser for the script.
    """

    arg_desc = '''\
        Let's scrape some torque accounting logs, Yay!
        ----------------------------------------------
            This program scrapes through torque 
            accounting logs and writes relevant information
            to a output .csv file.
        '''

    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
                                     description = arg_desc)

    parser.add_argument("-p","--pat", dest = "torque_path", default="/var/spool/torque/server_priv/accounting", 
                        help = "Path to torque accounting logs")
    parser.add_argument("-w","--window", dest="past_window", default=30, type=int,
                        help = "Number of days to look back in time")
    parser.add_argument("-s","--server_logs", dest="server_logs", default=False, action="store_true",
                        help = "Are the input files server logs instead of accounting logs?")                    

    args = parser.parse_args()

    # Return input
    return args.torque_path, args.past_window, args.server_logs



## ---------------------- Main --------------------- ##

def main():

    # Parse arguments
    torque_path, past_window, server_logs = parse_args()

    # Hard-coded variables
    today = datetime.datetime.today().strftime("%Y%m%d") # Today's date
    start_date = (datetime.datetime.today() - datetime.timedelta(days=past_window)).strftime("%Y%m%d") # Start date
    output_file = "/users/people/alexpil/torque_data.csv" # Output file


    # Get list of dates in the format of the torque accounting file
    date_list = build_date_list(start_date, today)

    # create the output file
    with open(output_file, "w") as outfile:
        outfile.write(",".join(["date", "User",
                                "exit_status", "ngpus", "nproc",
                                "walltime_req_sec", "walltime_sec",
                                "mem_req_mb", "mem_mb",
                                "cput_req_sec", "cput_sec"]) + "\n")

    # Go through the list of dates and extract the information
    for date in date_list:

        # Extract information
        extract_torque_data(date, output_file, torque_path, server_logs)

    # Print a message to the user
    print("Done!")





# Run the main function
if __name__ == "__main__":

    main()