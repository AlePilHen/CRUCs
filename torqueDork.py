"""
    Author: Alexander Henriksen
    Data: December 2022
    Description: This script was made to plot compute statistics for users on the Translation server.
                 These statistics include memory and core efficiency as well as overall carbon load.
                 The script takes a .csv file as input.
                 Carbon load is calculated using the ScienceFarts module.
    
    Input:
        1) A .csv input file containing job logs from Torque
        2) A user name (optional)
        Flags:
            -u: User name
            -c: Dont calculate carbon load (default is to calculate it)
    Output:
        None - the script simply prints the results to the terminal.

    USAGE:
        python torqueDork.py <torque_logfile> -u <user> -m <metric>

    TO DO:
        - Combine different metrics into a single metric

    IDEAS:
        - Show reports based on the last month, week, day, etc.
        - Create a combined score which takes into account
            - Memory efficiency
            - CPU efficiency
            - Carbon load
        - Add a metric showing how much of the computation was performed at night.

"""

import plotext as plt
import pandas as pd
import argparse
import ScienceFarts 
import sys 
import os
import pdb


## ------------------- Functions ------------------- ##

def my_own_plotter(x, y, title, m):
    """
    This is an attempt to make a plotter function which is similar to the one
    in plotext. It is much simpler, but it does the job and hey, you don't
    need to install any packages on the server.
    """
    # Prepare some print-related stuff
    counter = 0
    width = 100
    scale = "Efficiency (used / requested resources)" if m != "carbon" else "Mean carbon load (gCO2e)"
    header_spaces = " " * (width - len(f" {scale}"))

    # Print the header
    #print( "---------------------------------------------")
    print(f"\033[94m----- {title} {'-' * (width - len(title))}\033[00m")
    print( "")
    print( "User      | ",scale, header_spaces, "|", sep="")
    print( "          |"," " * width, "|", sep="")

    # Print the data
    for name, value in zip(x,y):
        # Prepare some stuff
        value = round(value, 3)
        hashes = int(value * 100) if m != "carbon" else int(value / (max(y) * 1.2) * 100)
        start_space = 10 - len(name)
        remain_space = 100 - hashes - (3 + len(str(value)))

        ## And print it
        # Add a green color to the user with the best score
        if counter == 0:
            name = "\033[92m{}\033[00m".format(name)
            hashes = "\033[92m{}\033[00m".format(hashes * '=')
            print(f"{name}{start_space * ' '}| {hashes}  {value}{remain_space * ' '}|")
        # Boring old white for the rest
        else:
            print(f"{name}{start_space * ' '}| {hashes * '='}  {value}{remain_space * ' '}|")
        counter += 1


def compute_stats(data, metric, user=None):
    """
    This function formats the input data to match the desired output format.
    It then calculates the desired metric and returns the results.
    """
    
    # If metric is 'memory'
    if metric == 'memory':
        # Set columns containing memory data
        req_col = "mem_req_mb"
        used_col = "mem_mb"
        title = "Memory efficiency"

    elif metric == "cpus":
        # Set columns containing cpu data
        req_col = "cput_req_sec"
        used_col = "cput_sec"
        title = "CPU time efficiency"
    
    elif metric == "carbon":
        title = "Carbon load"

    
    ## Compute statistics
    if metric != "carbon":
        # Calculate efficiency of metrics memory and cpu
        data = data[["User", req_col, used_col]].copy()
        data.loc[:,"eff"] = data[used_col] / data[req_col]
        data.loc[:,"frac"] = data[req_col] / data.groupby("User")[req_col].transform(sum)
        data.loc[:,"result"] = data["eff"] * data["frac"]
        stats = data.groupby("User").sum().sort_values(by = "result", ascending = False)
        
        x,y = stats.index.values, stats["result"]
    
    else:
        # Compute carbon load
        #pdb.set_trace()
        carbon_load, nr_washes = compute_carbon_load(data)
        stats = carbon_load.T.rename(columns = {"carbon_load": "result"})
        stats = stats.sort_values(by = "result", ascending = True)
        y = stats.result.values
        x = stats.index.values
        

    # Return results
    # In case a user is specified, return the metric and the position of the user
    
    if user:
        pos = stats.index.get_loc(user) + 1
        score = stats.loc[user,"result"]
        return(score, pos)
    # In case no user is specified, return a data frame with the metric for all users
    else:
        return(x,y,title)


def convert_seconds_to_datetimeString(seconds):
    """
    Convert seconds integer to HH:MM:SS format
    """

    min, sec = divmod(seconds, 60)
    hour, min = divmod(min, 60)

    return '%d:%02d:%02d' % (hour, min, sec)


def compute_carbon_load(data):
    """
    This function computes the carbon load for different users.
    It uses the amazing ScienceFarts module to do this. Wow!
    """

    # First extract data and reformat it for ScienceFarts
    # We use the mean of the last 100 jobs for that user
    user_data = data.groupby("User").tail(100).groupby("User").mean().round(0).astype(int)
    
    users = user_data.index.values
    cpus = user_data["nproc"]
    mem_gb = (user_data["mem_req_mb"] / 1000).astype(int)
    walltime =  user_data["walltime_sec"].apply(lambda row: convert_seconds_to_datetimeString(row))

    # Compute carbon load
    carbon_load = {}
    for walltime, mem_gb, cpus, user in zip(walltime, mem_gb, cpus, users):
        carbon, nr_washes = ScienceFarts.ScienceFarts([walltime, mem_gb, cpus], "forecast_return").run()
        carbon_load[user] = {"carbon_load": int(carbon), "nr_washes": round(nr_washes, 0)}
    carbon_load = pd.DataFrame.from_dict(carbon_load)

    return(carbon_load, nr_washes)


def plot_statistics(x, y, title, m):
    """
    This function plots statistics to the terminal.
    """
    # Use plotext to plot the data
    #plt.simple_bar(x, y, width = 100, title = title)
    #plt.show()

    # Use my own function to plot the data
    my_own_plotter(x, y, title, m)


def parse_args():
    """
    Argument parser for the script.
    """

    arg_desc = '''\
        Let's calculate your compute statistics, Yay!
        ---------------------------------------------
            This program will look through recent
            Torque log files, calculate statistics
            related to user computation and then 
            return the statistics as a plot.
        '''

    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
                                     description = arg_desc)

    parser.add_argument(dest = "Torque_file", nargs=1, 
                        help = "A .csv file containing compute metrics")
    parser.add_argument("-u","--user", dest="user", nargs=1, default=None,
                        help = "Produce a report for the specified user.")
    parser.add_argument("-c","--no_carbon", dest="carbon", action="store_false", 
                        default=True, help="Do not compute carbon load.")

    args = parser.parse_args()
    
    # Modify input
    torque_file = args.Torque_file[0]
    carbon = args.carbon
    user = args.user[0] if args.user else None

    # Check if input file exists
    if not os.path.isfile(torque_file):
        print("ERROR: The input file does not exist.")
        sys.exit()

    # Return input
    return(torque_file, user, carbon)


## ------------------- Main ------------------- ##

def main():
    # Get the input file
    input_file, user, carbon = parse_args()

    # Read the input file
    data = pd.read_csv(input_file, sep = ',')

    # Check if user exists
    if user not in data.User.values and user is not None:
        print(f"ERROR: The user '{user}' does not exist in the log file.")
        sys.exit()

    # Prepare metrics 
    if carbon:
        metric = ["memory", "cpus", "carbon"]
    else:
        metric = ["memory", "cpus"]

    # If user-specific data is requested, prepare a dict to store user results
    if user:
        user_dat = {"memory": {"score": None, "position": None},
                    "cpus": {"score": None, "position": None}}
        if carbon:
            user_dat["carbon"] = {"score": None, "position": None}
    
    # Iterate over metrics and produce plots / report data
    for m in metric:

        # If the user is specified, produce data for a report
        if user:
            score, pos = compute_stats(data, m, user)
            user_dat[m]["score"] = round(score,3)
            user_dat[m]["position"] = str(int(pos))

        # Otherwise, produce a plot
        else:
            x,y,title = compute_stats(data, m)
            plot_statistics(x,y,title, m)
            print("")
            print("")
    
    # Produce user report
    if user:
        user_data = pd.DataFrame(user_dat)
        user_data.columns = ["Memory", "CPU time", "Carbon"] if carbon else ["Memory", "CPU time"]
        user_data.index = ["Efficiency", "Rank"]

        user = "\033[95m{}\033[00m".format(user)
        print( "---------------------------------------------")
        print(f" Computation statistics for: {user}")
        print( "")
        print(user_data[["Memory","CPU time"]].T)
        print( "")
        if carbon:
            print(user_data.T.loc["Carbon":].rename(columns = {"Efficiency" : "Mean carbon load (gCO2e)"}))
            print( "---------------------------------------------")
            


# Run the main function
if __name__ == "__main__":

    main()