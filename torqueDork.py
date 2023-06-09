"""
    Author: Alexander Henriksen
    Date: December 2022
    Description: This script was made to plot compute statistics for users on the Translation server.
                 These statistics include memory and core efficiency as well as overall carbon load.
                 This script gathers data from a pre-defined sqlite database.
                 Carbon load is calculated using the ScienceFarts module.

    Input:
        1)  A path to a sqlite database file (optional)
        Flags:
            -d: Database path - in case you don't want to use the default.
            -p: Period - How many days into the past should data be collected?
            -u: User name
            -c: Dont calculate carbon load (default is to calculate it)
    Output:
        None - the script simply prints the results to the terminal.

    USAGE:
        python torqueDork.py  -u <user_name> -p <days>

    TO DO:
        - Combine different metrics into a single metric
        - Add default file to read from (scrapeTorque.py output)

    IDEAS:
        - Change output of scrapeTorque.py so that the output is
          summary statistics and so that TorqueDork.py simply
          reads that summary and presents it.
        - Show reports based on the last month, week, day, etc.
        - Create a combined score which takes into account
            - Memory efficiency
            - CPU efficiency
            - Carbon load
        - Add a metric showing how much of the computation was performed at night.
        - Calculate cput efficiency based on used_cput / (used_walltime * nproc)

"""

#import plotext as plt
import shutil
import getpass
import sqlite3
import argparse
import sys
import os
import pdb
import pandas as pd

# Try to import ScienceFarts
try:
    import ScienceFarts
    #from def_print_user_results import print_user_results
except ImportError:
    print("ScienceFarts is not installed. Please install it to compute carbon load.")


## ------------------- Functions ------------------- ##

def format_numeric_result(number):
    """
    Format numbers to output print.
    This includes rounding and adding thousand separators.
    """

    # For small numbers
    if number <= 1:
        out_number = str(round(number, 2))
    # For large numbers
    else:
        out_number = "{:,}".format(int(number))

    return out_number


## ------------------- Classes ------------------- ##

class torqueDork(object):
    """
    This class is used to compute statistics from the torque log data.
    The queried data is stored in the self.query_data variable.
    The computed statistics are stored in the self.data_stats variable.
    """

    def __init__(self, db_path, user, period, carbon, top_n):
        self.db_path = db_path
        self.query_user = user
        self.period = period
        self.carbon = carbon
        self.top_n = top_n
        self.query_data = None
        self.data_stats = None

    ## ------------------- Main ------------------- ##

    def main(self):
        """
        This function performs the main tasks of the script.
        Namely, it queries the torque database and computes efficiency metrics.
        """

        # Retrieve data from torque_log database
        self.query_data = self.query_torque_database()
        #data = pd.read_csv(input_file, sep = ',', index_col=False)

        # Check if user exists
        if self.query_user not in self.query_data.user.values and self.query_user is not None:
            print(f"ERROR: The user '{self.query_user}' does not exist in the log file.")
            sys.exit()

        # Compute stats from log data
        self.data_stats = self.compute_stats()



    ## ------------------- Functions ------------------- ##

    ## --- Query torque database for log data --- ##
    def query_torque_database(self):
        """
        Extract the requested data from the torque_log database.
        """

        # Open connection to database
        conn = sqlite3.connect(self.db_path,
                            detect_types=sqlite3.PARSE_DECLTYPES |
                            sqlite3.PARSE_COLNAMES)

        # Extract data
        # in case of a defined user
        if self.query_user is not None:
            data = pd.read_sql_query(f"""SELECT * from torque_logs
                                        WHERE logdate >= date('now', '-{self.period} day') 
                                        AND user = '{self.query_user}'""",
                                        conn)
        else:
            data = pd.read_sql_query(f"""SELECT * from torque_logs
                                        WHERE logdate >= date('now', '-{self.period} day')""",
                                        conn)

        # See if extracted dataframe is empty
        if data.empty:
            print(f"-- No data in the past {self.period} days. Try again")
            sys.exit(1)

        # Close database connection
        conn.close()

        return data



    ## --- Compute statistics from log data --- ##
    def compute_stats(self):
        """
        This function calculates efficiency metrics and other results from the
        torque log data. It then formats it and returns it as a pandas dataframe.
        """

        ## Compute statistics
        mem_eff = self.calculate_mem_efficiency(self.query_data[["user", "mem_req_mb", "mem_mb"]])
        cpu_eff = self.calculate_cpu_efficiency(self.query_data[["user", "walltime_sec", "cput_sec", "nproc"]])

        if self.carbon:
            # Compute carbon load
            #pdb.set_trace()
            carbon_load = self.compute_carbon_load(self.query_data)
            co2_eff = carbon_load.T

        ## Concat results to a single data frame
        if self.carbon:
            data_stats = pd.concat([mem_eff, cpu_eff, co2_eff], axis = 1)
        else:
            data_stats = pd.concat([mem_eff, cpu_eff], axis = 1)

        # Rename index
        data_stats.index.names = ["User"]

        return data_stats



    def calculate_mem_efficiency(self, data):
        """
        Calculate memory efficiency. Return results as a pandas dataframe.
        """

        # Calculate efficiency
        data = data[["user", "mem_req_mb", "mem_mb"]].copy()
        data.loc[:,"eff"] = data["mem_mb"] / data["mem_req_mb"]
        data.loc[:,"frac"] = data["mem_req_mb"] / data.groupby("user")["mem_req_mb"].transform(sum)
        data.loc[:,"mem_eff"] = data["eff"] * data["frac"]

        # Sort and clip at 1
        stats = data.loc[:, ["user", "mem_eff"]].groupby("user").sum()
        stats.loc[:,"mem_eff"] = stats["mem_eff"].clip(upper=1)

        return stats



    def calculate_cpu_efficiency(self, data):
        """
        Calculate cpu efficiency. Return results as a pandas dataframe.
        """

        # Calculate efficiency
        data = data[["user", "walltime_sec", "cput_sec", "nproc"]].copy()
        data.loc[:,"requested"] = data["walltime_sec"] * data["nproc"]
        data.loc[:,"eff"] = data["cput_sec"] / data["requested"]
        data.loc[:,"frac"] = data["requested"] / data.groupby("user")["requested"].transform(sum)
        data.loc[:,"cpu_eff"] = data["eff"] * data["frac"]

        # Sort and clip at 1
        stats = data.loc[:, ["user","cpu_eff"]].groupby("user").sum()
        stats.loc[:,"cpu_eff"] = stats["cpu_eff"].clip(upper=1)

        return stats



    def convert_seconds_to_datetimeString(self, seconds):
        """
        Convert seconds integer to HH:MM:SS format
        """

        min, sec = divmod(seconds, 60)
        hour, min = divmod(min, 60)

        return '%d:%02d:%02d' % (hour, min, sec)



    def compute_carbon_load(self, data):
        """
        This function computes the carbon load for different users.
        It uses the amazing ScienceFarts module to do this. Wow!
        """

        # First Caluclate the total resource use per user
        record_sums = data.drop('cput_sec', axis=1).groupby('user').sum()
        cput_mean = data.groupby('user')['cput_sec'].mean()

        user_data = pd.concat([record_sums, cput_mean], axis=1)

        # Define variables
        users    =  user_data.index.values
        cpus     =  user_data["nproc"]
        gpus     =  user_data["ngpus"]
        mem_gb   = (user_data["mem_req_mb"] / 1000).astype(int)
        walltime =  user_data["cput_sec"].apply(lambda row: self.convert_seconds_to_datetimeString(row))

        # Compute carbon load
        carbon_load = {}
        # Loop over users and their metrics
        for walltime, mem_gb, cpus, gpus, user in zip(walltime, mem_gb, cpus, gpus, users):

            # Compute carbon load with ScienceFarts
            carbon_obj = ScienceFarts.ScienceFarts([walltime, mem_gb, cpus, gpus], "forecast")
            carbon_obj.run()
            carbon_stats = carbon_obj.stats_out

            # Format results and add to dictionary
            carbon_kg = carbon_stats["total_emissions"] / 1000 # Change carbon unit from g to kg
            car_km = carbon_stats["rel_car_1km"]
            carbon_load[user] = {"carbon_load": int(carbon_kg)}# , "car_km": round(car_km, 0)}

        carbon_load = pd.DataFrame.from_dict(carbon_load)

        return carbon_load




### ------------------- Plotting functions ------------------- ###

## ------ Currently not used ----- ##
def plotext_plotter(x, y, title, m):
    """
    Plot results using the plotext module
    """
    terminal_width = plt.tw() - 10

    if m != "carbon":
        plt.simple_bar(x, y, width = terminal_width, title = title)
        plt.xlim(0,1)
        plt.show()
    else:
        plt.simple_bar(x, y, width = terminal_width, title = title)
        plt.show()



def print_user_report(df, show_carbon = True):
    """
    Prints a smallreport with memory and cpu time statistics
    for a specific user.
    """

    # Define data and reformat data
    user_data = df
    user_data.loc[:,"mem_eff"] = round(user_data.loc[:,"mem_eff"] * 100, 2)
    user_data.loc[:,"cpu_eff"] = round(user_data.loc[:,"cpu_eff"] * 100, 2)
    user_data = user_data.T

    # Add units
    if show_carbon:
        units = pd.DataFrame({"mem_eff": " %", "cpu_eff": " %", "carbon_load": " kgCO2e"}, index = ["unit"]).T
    else:
        units = pd.DataFrame({"mem_eff": " %", "cpu_eff": " %"}, index = ["unit"]).T
    user_data = pd.concat([user_data, units], axis = 1)

    # Print results
    user = f"\033[95m{query_user}\033[00m"
    print( "---------------------------------------------")
    print(f" Computation statistics for: {user}")
    print( "")
    print(user_data)
    print( "")




## --- Plot statistics to screen --- ##
def print_results(df, query_user, top_n = 5):
    """
    Prints a horizontal bar graph in the terminal for each user based on their 'Result' value,
    sorted by rank from highest to lowest. The top_n entries are printed by default,
    but a specific user can be specified with the 'name' parameter.
    The top entry is printed in green color, and the entry matching 'name' (if provided)
    is printed in blue/cyan color.

    Args:
        df (pandas.DataFrame): The input DataFrame containing two columns: 'User' and 'Result'.
        metric (string) the metric to plot (memory, CPU time, or carbon).
    """

    # Loop over metrics
    for metric in df.columns:

        # Set title and sort DataFrame
        if metric == 'mem_eff':
            title  = "Memory efficiency \U0001F40F"
            df_metric = df.copy().sort_values(metric, ascending=False)
        elif metric == 'cpu_eff':
            title  = "CPU efficiency \U0001F551"
            df_metric = df.copy().sort_values(metric, ascending=False)
        elif metric == 'carbon_load':
            title  = "Carbon load \U0001F4A8"
            df_metric = df.copy().sort_values(metric, ascending=True)

        # Move index to 'User' column and change index to rank
        df_metric.reset_index(inplace=True)

        # Get key values
        max_result = df_metric[metric].max()                        # MAX value
        terminal_width = shutil.get_terminal_size().columns - 10    # Terminal width
        current_user = getpass.getuser()                            # Current user

        # If 'name' is provided, find the index of the entry matching 'name' in the DataFrame
        name_index = None
        if query_user is not None:
            name_index = df_metric[df_metric['User'] == current_user].index

        # Calculate the maximum width for rank and username based on terminal width
        max_rank_width = len(str(df_metric.index.max() + 1)) + 4
        max_username_width = 10
        max_result_width = (df_metric[metric] * 100).apply(lambda x: f"{x:.2%}" if metric != 'carbon' else f"{x}").str.len().max()
        max_bar_length = terminal_width - max_rank_width - max_username_width - max_result_width - 10

        # Limit df to top entries and the entry matching self.name
        df_top = df_metric.head(top_n)
        if current_user not in df_top['User'].values:
            print(current_user)
            df_top = pd.concat([df_top, df_metric[df_metric['User'] == current_user]])

        # Print the header
        scale = "Efficiency (used / requested resources)" if metric != "carbon_load" else "Total carbon load (kgCO2e)"
        print("")
        print(f"\033[94m----- {title} {'-' * (terminal_width - len(title))}\033[00m")
        print( "")
        print(f" Rank  Username   | {scale}{' ' * (max_bar_length - len(scale) - 1)}")

        # Loop through each row in the DataFrame and print the top entries or the entry matching 'name'
        for index, row in df_top.iterrows():
            rank = index + 1  # Rank starts from 1
            username = row['User']
            result = row[metric]

            # Calculate the length of the bar based on the 'Result' value and maximum bar length
            if metric == 'carbon_load':
                max_result = df_metric[metric].max()
                bar_length = int(result * max_bar_length / max_result)
            else:
                bar_length = int(result * max_bar_length)

            # Pad the rank and username with spaces for alignment
            padded_rank = str(rank).rjust(max_rank_width)
            padded_username = username.ljust(max_username_width)

            # Determine the color for printing based on the rank, username, and 'name' parameter
            if rank == 1:
                rank_color = '\033[32m'  # Green color for the top entry
            elif username == current_user:
                rank_color = '\033[94m'  # Purple color for the current user's entry
            elif name_index is not None and index in name_index:
                rank_color = '\033[94m'  # Purple color for the entry matching 'name'
            else:
                rank_color = '\033[0m'   # Default color for remaining entries


            # Print the rank, username, the horizontal bar with the 'Result' value ,
            if metric == 'carbon_load':
                print(f"{rank_color}{padded_rank}. {padded_username} |{'=' * bar_length}{' ' * (max_bar_length - bar_length)}| {result:,}")
            else:
                print(f"{rank_color}{padded_rank}. {padded_username} |{'=' * bar_length}{' ' * (max_bar_length - bar_length)}| {result:.2%}")

        # Reset color to default after printing
        print('\033[0m')



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

    parser.add_argument("-d","--database", dest = "Database_path", default="./test_db.db",
                        help = "A path to the torque_log database")
    parser.add_argument("-u","--user", dest="user", nargs=1, default=None,
                        help = "Produce a report for the specified user.")
    parser.add_argument("-p","--period", dest="period", default=30, type=int,
                        help = "The number of days into the past you want to summarize data for.")
    parser.add_argument("-c","--no_carbon", dest="carbon", action="store_false",
                        default=True, help="Do not compute carbon load.")
    parser.add_argument("-t","--top_users", dest="top_users",type=int,
                        default=5, help="How many users should be shown. Default is 5")

    args = parser.parse_args()

    # Modify input
    database_path = args.Database_path
    carbon      = args.carbon
    user        = args.user[0] if args.user else None
    period      = args.period #if args.period < 730 else 30
    top_n       = args.top_users

    # Check if input file exists
    if not os.path.isfile(database_path):
        print("ERROR: The input database path does not exist.")
        sys.exit()

    # Return input
    return(database_path, user, period, carbon, top_n)



## BEGIN
if __name__=="__main__":

    # Parse input
    db_path, query_user, period, carbon, top_n = parse_args()
    USER = "Alex"


    # Run program
    cd = torqueDork(db_path, query_user, period, carbon, top_n)
    cd.main()

    # Print results to terminal
    if query_user:
        print_user_report(cd.data_stats, carbon)
    else:
        print_results(cd.data_stats, USER, top_n)
