"""
    Author: Alexander Henriksen
    Data: February 2023
    Description: This script was made to scrape a set of toque accounting files
                 to extract all information on use of CPUs, memory and time.
                 It then outputs this information into a sqlite database, which can 
                 be used by the torqueDork.py script to calculate statistics.
    
    Input:
        1) A torque accounting file (-p)
        2) A target sqlite database in which to put the output (-l)
        Flags:
          -p: Path to the torque accounting files
          -l: Path to the output sqlite database
          -w: Time window - Number of days into the past that the script should scrape data
          -s: Server logs - Are the input files server_logs instead of accounting_logs?
    Output:
        1) A torque_logs.db sqlite database containing job information
           
    USAGE:
        python scrapeTorque.py <torque_logfile> 

    IDEAS:
        - Create a second table that includes summary statistics for each user.
          This could be ordered by Year, Month, Week and so on.
          This would mean that calling torqueDork doesn't require a calculation
          of summary stats, but simply a retrieval of them
"""

import pandas as pd
import datetime
import argparse
import sqlite3
import math
import sys 
import os
import re
import pdb

## ------------------- Definitions ------------------- ##

class ScrapeTorque(object):

    def __init__(self, torque_path, log_path, past_window, server_logs):
        self.torque_path = torque_path
        self.log_path = log_path
        self.past_window = past_window
        self.server_logs = server_logs

    ## ---------------------- Run --------------------- ##

    def run(self):

        # Open database
        conn, cursor, last_date = self.check_database()

        # Hard-coded variables
        today = datetime.datetime.today().date() #strftime("%Y%m%d") # Today's date
        #start_date = (datetime.datetime.today() - datetime.timedelta(days=self.past_window)).strftime("%Y%m%d") # Start date
        #output_file = "/users/people/alexpil/torque_data.csv" # Output file


        # Get list of dates in the format of the torque accounting file
        torque_file_list = self.build_date_list(last_date, today)

        # Go through the list of dates and extract the information
        print(f"-- Updating database with logs since {last_date} --")
        for torque_file in torque_file_list:

            # Extract information and add to database
            self.extract_torque_data(torque_file, conn, cursor)


        # Commit and close connection
        conn.commit()
        conn.close()

        # Print a message to the user
        print("-- Done!")



    ## ------------------- Functions ------------------- ##

    def check_database(self):
        """
        Check if the database exists and create if it doesn't
        """

        database = self.log_path
        if not os.path.exists(database):
            print(f"Error: {database} does not exist.")
            exit(1)

        # Connect to the database
        conn = sqlite3.connect(database,
                               detect_types=sqlite3.PARSE_DECLTYPES |
                               sqlite3.PARSE_COLNAMES)
        cursor = conn.cursor()

        # Check for the existence of a table and create the raw table if it doesn't exist
        cursor.execute("""CREATE TABLE IF NOT EXISTS torque_logs (
                            logdate date,
                            user text,
                            exit_status integer,
                            ngpus integer,
                            nproc integer,
                            walltime_req_sec integer,
                            walltime_sec integer,
                            mem_req_mb integer,
                            mem_mb integer,
                            cput_req_sec integer,
                            cput_sec integer
                            )""")

        # Get latest date from database
        last_date = self.get_last_database_date(conn, cursor)

            
        return conn, cursor, last_date


    def get_last_database_date(self, conn, cursor):
        """
        Fetch the date of the last data entry in the database
        """

        # Fetch the date of the latest data entry
        cursor.execute("SELECT logdate FROM torque_logs")
        dates = [datelist[0] for datelist in cursor.fetchall()]

        # In case of no info in database, start at 01.01.2023
        if len(dates) == 0:
            last_date = datetime.datetime.strptime("20200101", "%Y%m%d")
        else:
            last_date = sorted(dates, 
                                #key = lambda d: datetime.datetime.strftime(d, "%Y%m%d"),
                                reverse=True)[0]
        
        print(f"-- Latest date in the database is {last_date} --")

        return last_date


    def walltime_to_seconds(self, walltime):
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


    def memory_to_mb(self, memory):
        """
        This function takes a memory request in the format of the torque accounting file
        (e.g. 10gb) and converts it to MB.
        """

        # In case no memory was requested, assume a full node (180gb)
        if memory == "1":
            return str(180 * 1024)

        # Extract the memory amount and the unit
        mem_match = re.match(r"([0-9]+)([a-z]+)", memory)
        memory_amount = int(mem_match.group(1))
        memory_unit   =     mem_match.group(2)
        
        # Convert to MB
        if memory_unit == "gb":
            memory = memory_amount * 1024
        elif memory_unit == "mb":
            memory = memory_amount
        elif memory_unit == "kb":
            memory = memory_amount / 1024
        elif memory_unit == "b":
            memory = memory_amount / 1024 / 1024
            memory = math.ceil(round(memory))

        return str(round(memory))

    def get_line_match(self, name, pattern, string):
        """
        This function takes a string and a pattern and returns
        a regex match. If no match is found, it returns 0.
        """

        match = re.search(pattern, string)
        if match:
            return match.group(1)
        elif not match and name == "user":
            return "server"
        elif not match and name == "req_gpus":
            return "0"
        else:
            return "1"


    def build_date_list(self, start_date, end_date):
        """
        This function takes two dates in the format of the torque accounting file
        and returns a list of dates in the same format.
        """
        # Convert the dates to datetime objects
        start_date = datetime.datetime.strftime(start_date, "%Y%m%d")
        end_date = datetime.datetime.strftime(end_date, "%Y%m%d")

        # Create a list of dates between the two dates
        date_list = []
        for date in pd.date_range(start_date, end_date, inclusive="right"):
            date_list.append(date.strftime("%Y%m%d"))

        return date_list


    def extract_torque_data(self, date, conn, cursor):
        """
        This function goes through a torque accounting file and extracts
        relevant information on resource use.
        """

        torque_file = os.path.join(self.torque_path, date)

        # Check if the file exists
        if not os.path.isfile(torque_file):
            print("File {} does not exist.".format(torque_file))
            return

        # Open the torque accounting file
        with open(torque_file, "r") as infile:
        #open(output_file, "a") as outfile:

            # Go through the file line by line
            for line in infile:

                # Find lines with information on ended jobs
                if re.search("Exit_status=-*\d+", line):

                    # extract line
                    #line = line.strip("\n").split(" ")

                    # Initialize dictionary
                    data = {}

                    # Define patterns to extract information
                    if self.server_logs:
                        patterns = {"date":          "(^[0-9/]{10})",
                                    "user":          "user=(\w+)",
                                    "exit_status":   "Exit_status=(\d+)",
                                    "req_cpus":      "Resource_List.+ppn=(\d+)",
                                    "req_gpus":      "Resource_List.+gpu=(\d+)",
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
                                    "req_gpus":      "Resource_List.+gpus=(\d+)",
                                    "used_walltime": "resources_used\.walltime=([0-9:]+)",
                                    "used_mem":      "resources_used\.mem=(\d+\w+)",
                                    "used_cput":     "resources_used\.cput=(\d+)"}

                    # Extract information
                    for name in patterns.keys():
                        data[name] = self.get_line_match(name, patterns[name], line)
                
                    # In case of server logs as input some values will need to be changed
                    # as these are not present in the log files.
                    if self.server_logs:
                        data["req_walltime"] = data["used_walltime"]
                        data["req_mem"] = data["used_mem"]

                    # Format extracted data for output
                    logdate = datetime.datetime.strptime(data["date"], "%m/%d/%Y").date()
                    req_walltime = self.walltime_to_seconds(data["req_walltime"])
                    used_walltime = self.walltime_to_seconds(data["used_walltime"])
                    req_mem = self.memory_to_mb(data["req_mem"])
                    used_mem = self.memory_to_mb(data["used_mem"])

                    if self.server_logs:
                        data["req_cpus"] = str(round(int(data["used_cput"]) / int(used_walltime)+1))

                    # Calculate required cputime
                    if self.server_logs:
                        req_cputime = str(int(req_walltime) * int(data["req_cpus"]))
                    else:
                        req_cputime = str(int(req_walltime) * int(data["req_cpus"]) * int(data["req_nodes"]))

                    # Add info to database
                    cursor.execute("""INSERT INTO torque_logs 
                                      VALUES 
                                       (:logdate, :user, :exit_status, :ngpus, :nproc,
                                       :walltime_req_sec, :walltime_sec, :mem_req_mb,
                                       :mem_mb, :cputime_req_sec, :cputime_sec)""", 
                                       {"logdate": logdate, "user": data["user"],
                                        "exit_status": data["exit_status"], "ngpus": data["req_gpus"],
                                        "nproc":data["req_cpus"], "walltime_req_sec": req_walltime,
                                        "walltime_sec": used_walltime, "mem_req_mb": req_mem,
                                        "mem_mb": used_mem, "cputime_req_sec":  req_cputime,
                                        "cputime_sec":data["used_cput"]})

        # Print message after data extract            
        print(f" > Updated database with info from {date}")



 ## ---------------------- Parse args and run --------------------- ##

def parse_args():
    """
    Argument parser for the script.
    """

    arg_desc = '''\
        Let's scrape some torque accounting logs, Yay!
        ----------------------------------------------
            This program scrapes through torque 
            accounting logs and writes relevant information
            to a sqlite3 database
        '''

    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
                                    description = arg_desc)

    parser.add_argument("-p","--path", dest = "torque_path", default="/var/spool/torque/server_priv/accounting", 
                        help = "Path to torque accounting logs")
    parser.add_argument("-l","--log", dest="log_path", default="/var/spool/torque/server_priv/accounting",
                        help = "Path to output/input log file")
    parser.add_argument("-w","--window", dest="past_window", default=7, type=int,
                        help = "Number of days to look back in time")
    parser.add_argument("-s","--server_logs", dest="server_logs", default=False, action="store_true",
                        help = "Are the input files server logs instead of accounting logs?")                    

    args = parser.parse_args()

    # Return input
    return args.torque_path, args.log_path, args.past_window, args.server_logs


## BEGIN
if __name__=="__main__":
    
    # Parse input
    torque_path, log_path, past_window, server_logs = parse_args()
    
    # Run program
    cd = ScrapeTorque(torque_path, log_path, past_window, server_logs)
    cd.run()