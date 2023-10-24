"""
    Author: Alexander Henriksen
    Date: Began July 2022, updated continuously.
    Description: This script calculates the energy use and carbon emissions related
                 to a job submitted to the torque queing system. It uses historical
                 energy price and emissions data to make this calculation. ScienceFarts
                 can be run on both single jobids but also at the end of a snakemake
                 pipeline. Results are printed to the screen.

    Input:
        1)  A job_id or the path to a snakemake logfile
        Flags:
            -a: Flag to show that this job_id an array_id
            -l: Flag to show that the input is a snakemake logfile
            -f: Forecast - Show expected emissions of a job.
                Requires the following variables:
                -t: Expected walltime in format "HH:MM:SS"
                -m: Amount of memory in format "Xgb"
                -c: Number of CPUs (cores)
                -g: Number of GPUs
    Output:
        None - the script simply prints the results to the terminal.
        However, the ScienceFarts class can be imported and used to get the results.
        These are stored in the self.stats_df and self.stats_out variables.
        The former contains all the stats related to specific jobs, while the latter
        contains the aggregated stats for all jobs.

    USAGE:
        python ScienceFarts.py  <job_id>
"""

import argparse
import datetime
import math
import os
import re
import sys
import subprocess
import yaml
import pandas as pd
import pdb

## --------------------------------------------------------- ##
##                       HELPER FUNCTIONS                    ##
## --------------------------------------------------------- ##


## --- Function for converting memory to GB
def convert_memory_to_gb(memory):

    # Convert to GB
    # Asuume MB if no unit is given
    try:
        memory = int(memory) / 1000
    except ValueError:
        if memory[-2:] == 'kb':
            memory = int(memory[0:-2]) / 1000000
        elif memory[-2:] == 'mb':
            memory = int(memory[0:-2]) / 1000
        elif memory[-2:] == 'gb':
            memory = int(memory[0:-2])
        elif memory[-2:] == 'tb':
            memory = int(memory[0:-2]) * 1000
        else:
            print(f"Memory unit {str(memory[-2:])} not recognized. Please use kb, mb, gb or tb")
            sys.exit()

    return memory


## --------------------------------------------------------- ##
##                   MAIN CLASSES / FUNCTIONS                ##
## --------------------------------------------------------- ##


class ForecastStats():

    """
    This class handles the forecast stats.
    It converts input forecast stats to a dataframe which can be used by the ScienceFarts class.
    The class adds the stats to a pandas dataframe stored in the class (self.stats_df)
    """

    def __init__(self, user_args):
        self.walltime = user_args[0]
        self.memory = user_args[1]
        self.cores = user_args[2]
        self.gpus = user_args[3]
        self.stats_df = self.run()

    ## -- Function to handle forecast stats
    def run(self):

        # Convert walltime to start and end time
        starttime, endtime, walltime = self.get_start_end_time(self.walltime)

        # Convert memory to GB
        memory = convert_memory_to_gb(self.memory)

        # Calculate CPU time
        cpu_time = self.get_cpu_time(self.walltime, self.cores)

        # Create dataframe
        stats_df = pd.DataFrame({'start_time': starttime,
                                 'end_time':   endtime,
                                 'cores':      self.cores,
                                 'gpus' :      self.gpus,
                                 'memory_gb':  memory,
                                 'cpu_time':   cpu_time,
                                 'walltime':   walltime}, index=[0])

        return stats_df


    ## --- Function for calculating CPU time
    def get_cpu_time(self, walltime, cores):

        # Get walltime components
        walltime = walltime.split(':')
        hours = int(walltime[0])
        minutes = int(walltime[1])
        seconds = int(walltime[2])

        # Convert to seconds
        walltime = (hours * 3600) + (minutes * 60) + seconds

        # Calculate CPU time
        cpu_time = walltime * cores

        return cpu_time


    ## --- Function for converting walltime to start and end time
    def get_start_end_time(self, walltime):

        # Get current time
        now = datetime.datetime.now()

        # Get walltime components
        walltime = walltime.split(':')
        hours = int(walltime[0])
        minutes = int(walltime[1])
        seconds = int(walltime[2])

        # Convert to timedelta
        walltime = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

        # Calculate end time
        endtime = now + walltime

        return now, endtime, walltime




class JobStats():

    """
    This class handles the job IDs.
    It queries the job IDs in the torque logs and extracts the necessry stats to calculate resource use.
    It can handle both single job IDs and array IDs.
    The class adds the stats to a pandas dataframe stored in the class (self.stats_df)
    """

    def __init__(self, user_input, input_type, past_window=90):
        self.user_input = user_input
        self.input_type = input_type
        self.past_window = past_window
        self.stats_df = self.run()


    ## -- Main function for running the class
    def run(self):

        if self.input_type in ['jobid', 'jobarray']:
            self.id_array = self.user_input
            stats_df = self.get_tracejob_figures()
        else:
            self.id_array = self.get_ids_from_logfile()
            stats_df = self.get_tracejob_figures()

        return stats_df


    ## -- Function to parse walltime
    def parse_walltime(self, walltime):

        # Get walltime components
        walltime = walltime.split(':')
        hours = int(walltime[0])
        minutes = int(walltime[1])
        seconds = int(walltime[2])

        # Convert to seconds
        walltime = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

        return walltime



    ## -- Function to extract jobids from a snakemake logfile
    def get_ids_from_logfile(self):

        ## Get times from log file
        with open(self.user_input, 'r') as file:

            id_list = []
            id_pattern = "Submitted job \d+ with external jobid '(\d{6})\."

            for line in file:

                log_id = re.search(id_pattern, line)

                if log_id:
                    id_list.append(log_id[1].strip())
        
        return id_list



    ## --- Function for getting resources used from torque/PBS log
    def get_tracejob_figures(self):

        # Create lists for storing log data
        start_time_list = []
        end_time_list = []
        cores_list = []
        memory_list = []
        cpu_time_list = []
        walltime_list = []

        for job_id in self.id_array:

            # Extract log for that jobid
            tracelog = subprocess.run(f"tracejob {job_id} -n {self.past_window} -alm",
                                    shell = True, stdout=subprocess.PIPE,
                                    check=True, stderr=subprocess.STDOUT)

            # Reformat log
            tracelog = tracelog.stdout.decode().split('\n')

            # Create lists for storing log data
            start_times = []
            walltimes   = []
            cpu_times   = []
            memories    = []
            end_times   = []

            # Iterate over log items
            for line in tracelog:

                start_time = None
                end_time = None

                line_start = re.search("Job Run at request of", line)
                line_resource = re.search("resources_used.", line)

                if line_start and not self.input_type == 'jobarray':
                    start_time = re.search("(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",line)[1]
                    start_time = datetime.datetime.strptime(start_time, "%m/%d/%Y %H:%M:%S")
                    start_times.append(start_time)

                if line_resource:

                    # Extract information
                    cpu_time = re.search("resources_used.cput=(\d+)",line)[1]
                    cpu_time = int(cpu_time)
                    cpu_times.append(cpu_time)

                    memory = re.search("resources_used.mem=(\d+\w+)",line)[1]
                    memory = convert_memory_to_gb(memory)
                    #memory = int(memory[0:-2])
                    memories.append(memory)

                    end_time = re.search("(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",line)[1]
                    end_time = datetime.datetime.strptime(end_time, '%m/%d/%Y %H:%M:%S')
                    end_times.append(end_time)

                    walltime = re.search("resources_used.walltime=(\d+:\d+:\d+)",line)[1]
                    walltime = self.parse_walltime(walltime)
                    walltimes.append(walltime)

                    # If the input is a jobarray then manually add times to start_times
                    # There is only a single line in the job log for jobarrays.
                    if self.input_type == "jobarray":
                        start_time = end_time - walltime
                        start_times.append(start_time)

                    # Skip remaining lines if input type is not jobarray
                    elif self.input_type != "jobarray":
                        break

            # If job has failed, no resources registered in the log file
            # Add end time and assume 1 core and 100 MB memory
            if start_time and not end_time:
                end_time = datetime.datetime.now()
                end_times.append(end_time)
                cpu_times.append(end_time - start_time)
                memories.append(100000)
                walltimes.append(end_time - start_time)

            # Estimate number of cores used and catch errors when jobID has no record
            try:
                cores = [ math.ceil(cpu_time / walltime.total_seconds()) for (cpu_time, walltime) in zip(cpu_times, walltimes) ]
                if len(cores) == 0:
                    raise UnboundLocalError
            except UnboundLocalError:
                print(f"Error: The jobID <{id}> does not appear in the logs of the past 90 days.", file = sys.stderr)
                print( "       Please try a different jobID or change the search window to look further into past logs.", file = sys.stderr)
                print(f"       If you are running ScienceFarts after a snakemake pipeline jobID {job_id} will not be included in the results.", file = sys.stderr)
                continue

            # Update lists
            start_time_list.extend(start_times)
            end_time_list.extend(end_times)
            cores_list.extend(cores)
            memory_list.extend(memories)
            cpu_time_list.extend(cpu_times)
            walltime_list.extend(walltimes)

        # In case no jobs were found
        if len(start_time_list) == 0:
            print("----------------------------------------------------------------------------------------", file = sys.stderr)
            print("NO JOBS FOUND. Please check your jobID and try again.", file = sys.stderr)
            print("Are you running ScienceFarts after a snakemake pipeline?", file = sys.stderr)
            print("Then the error may be because your pipeline failed before any rules/jobs were finished.", file = sys.stderr)
            print("----------------------------------------------------------------------------------------", file = sys.stderr)
            sys.exit(0)

        # combine lists to dataframe
        stats_df = pd.DataFrame({'start_time': start_time_list,
                                 'end_time':   end_time_list,
                                 'cores':      cores_list,
                                 'gpus' :      [0 for i in range(len(cores_list))],
                                 'memory_gb':  memory_list,
                                 'cpu_time':   cpu_time_list,
                                 'walltime':   walltime_list})


        return stats_df



class ScienceFarts():
    """
    This is the main ScienceFarts class. It takes a user input and determines
    whether it is a jobID, logfile or forecast. It then calls the appropriate
    class to process the input and generate the stats dataframe. The stats
    dataframe is then used to calculate resource use and emmisions. Finally,
    the results are returned and if __main__ they are printed to the screen.
    """

    def __init__(self, user_input, input_type, config_file = "config.yaml"):
        self.user_input       = self.format_user_input(user_input)
        self.input_type       = input_type
        self.config           = self.load_config(config_file)
        self.location         = self.config['cluster']['location']
        self.ref_dir          = os.path.abspath(os.path.join(os.path.dirname(__file__), 'reference_data/'))
        self.emission_refs    = os.path.join(self.ref_dir, "emission_references.yaml")
        self.carbon_intensity = self.determine_config_stats(self.location, stat = "intensity")
        self.energy_price, \
        self.price_currency   = self.determine_config_stats(self.location, stat = "price")
        self.stats_df         = None
        self.stats_out        = None

    ## --- Main function
    def run(self):

        # set wd
        file_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
        os.chdir(file_dir)

        # Determine whether user input job IDs, logfile or forecast
        # and act accordingly
        if self.input_type == "forecast":
            forecast = ForecastStats(self.user_input)
            self.stats_df = forecast.stats_df
        else:
            jobs = JobStats(self.user_input, self.input_type, past_window=90)
            self.stats_df = jobs.stats_df

        # Calculate resource use and emissions for each job
        self.calculate_resource_use()

        # Calculate total resource use and emissions
        self.calculate_total_resource_use()

        # Calculate emissions comparisons
        self.calculate_emission_comparisons()


    ## --- Load config file
    def load_config(self, config_file):

        with open(config_file, "r") as stream:
            try:
                cluster_info = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        
        return cluster_info
    

    ## --- Determine carbon intensity
    def determine_config_stats(self, location, stat):

        location = location.lower()

        # Fetch carbon intensity from config / reference file
        if stat == "intensity":

            if self.config['cluster']['carbon']['custom_intensity_file']:
                carbon_intensity = pd.read_csv(os.path.abspath(self.config['cluster']['carbon']['custom_intensity_file']),
                                                    delimiter='\t', names = [str(n) for n in range(0,24)])
            elif self.config['cluster']['carbon']['carbon_intensity']:
                carbon_intensity = self.config['cluster']['carbon']['carbon_intensity']
            else:
                carbon_intensities = pd.read_csv(os.path.abspath(self.config['cluster']['carbon']['carbon_ref']), delimiter='\t')
                carbon_intensity = carbon_intensities.loc[carbon_intensities['Country'] == location]['Carbon_intensity'].item()

            # Check if carbon intensity was found
            if carbon_intensity is None:
                print(f"Carbon intensity was not found. Please define it in the config file.")
                sys.exit()

            return carbon_intensity
        
        # Fetch carbon price from config / reference file
        elif stat == "price":

            if self.config['cluster']['price']['custom_price_table']:
                energy_price = pd.read_csv(os.path.abspath(self.config['cluster']['price']['custom_price_table']),
                                                    delimiter='\t', names = [str(n) for n in range(0,24)])
                price_currency = self.config['cluster']['price']['price_currency']
            else:
                energy_price = self.config['cluster']['price']['energy_price']
                price_currency = self.config['cluster']['price']['price_currency']

            # Check if energy price was found
            if energy_price is None or price_currency is None:
                print(f"Energy price/currency was not found. Please define it in the config file.")
                sys.exit()

            return energy_price, price_currency


    ## --- Format user input to avoid errors
    def format_user_input(self, user_input):

        # Add one second if walltime is 0:00:00
        walltime = "0:00:01" if user_input[0] in ["0:00:00", "00:00:00"] else user_input[0]

        # Add 1 gb if memory is 0
        memory = "1" if user_input[1] == "0" else user_input[1]

        # Add 1 core if cores is 0
        cores = "1" if user_input[2] == "0" else user_input[2]

        return [walltime, memory, cores, user_input[3]]
        

    ## --- Calculate resource use
    def calculate_resource_use(self):

        # Apply functions to dataframe to calculate different metrics
        self.stats_df["ram_sticks"]     = self.stats_df.apply(lambda row: math.ceil(row["memory_gb"] / 16), axis = 1)
        self.stats_df["cpu_efficiency"] = self.stats_df.apply(self.calculate_cpu_efficiency_row, axis = 1)
        self.stats_df["energy_kwh"]     = self.stats_df.apply(self.calculate_energy_row, axis = 1)
        self.stats_df["per_hour_kWh"]   = self.stats_df.apply(lambda row: row["energy_kwh"] / (row["walltime"].total_seconds() / 3600), axis = 1)
        self.stats_df["cost_DKK"]       = self.stats_df.apply(self.calculate_energy_price_row, axis = 1)
        self.stats_df["emissions_g"]    = self.stats_df.apply(self.calculate_emissions_row, axis = 1)



    ## --- Calculate total resource use
    def calculate_total_resource_use(self):

        # Calculate total CPU efficiency
        total_cpu_time   = round(sum(self.stats_df["cpu_time"]) / 3600, 2)
        job_rel_fraction = self.stats_df["cpu_time"] / total_cpu_time
        total_efficiency = sum(job_rel_fraction * self.stats_df["cpu_efficiency"])

        # Calculate total resource use
        total_energy_use = round(sum(self.stats_df["energy_kwh"]), 2)
        total_emissions  = round(sum(self.stats_df["emissions_g"]), 2)
        total_dkk        = round(sum(self.stats_df["cost_DKK"]), 2)


        # Add total resource use to output dictionary
        self.stats_out = {"total_cpu_time":   total_cpu_time,
                          "total_energy_use": total_energy_use,
                          "total_emissions":  total_emissions,
                          "total_dkk":        total_dkk,
                          "total_efficiency": total_efficiency}

        # Add additional information to output dictionary
        self.stats_out["global_time_start"] = min(self.stats_df["start_time"])
        self.stats_out["global_time_end"]   = max(self.stats_df["end_time"])
        self.stats_out["global_timespan"]   = round((self.stats_out["global_time_end"] - self.stats_out["global_time_start"]).total_seconds() / 3600, 2)

        # Calculate relative RAM use
        self.stats_out["ram_sticks_used"] = sum(self.stats_df["ram_sticks"])



    # --- Calculate CPU efficiency for a single row
    def calculate_cpu_efficiency_row(self, row):

        # Calculate CPU efficiency
        cpu_efficiency = row["cpu_time"] / row["cores"] / row["walltime"].total_seconds()

        return cpu_efficiency


    # --- Calculate energy use for a single row
    def calculate_energy_row(self, row):

        # Read reference values from reference file
        with open(self.emission_refs, "r") as file:
            reference_data = yaml.safe_load(file)

        # Calculate energy use
        energy_use_ram = row["cpu_time"] * row["ram_sticks"] * reference_data["energy"]["mem_16GB"]["kW"]
        energy_use_cpu = row["cpu_time"] * reference_data["energy"]["cpu_core"]["kW"]
        energy_use_gpu = row["gpus"] * row["walltime"].total_seconds() * reference_data["energy"]["gpu_full"]["kW"]

        energy_use_kWh = (energy_use_cpu + energy_use_ram + energy_use_gpu) / 3600

        return energy_use_kWh


    # --- Calculate energy price for a single row
    def calculate_energy_price_row(self, row):

        # Load reference data
        if isinstance(self.energy_price, pd.DataFrame): 
            price_ref_df = self.energy_price
        else:
            price_ref_df = None
            price_ref = self.energy_price

        ## Calculate price
        total_price = 0.0
        current_time = row["start_time"]

        while current_time <= row["end_time"]:
            # Get the weekday and hour values from the current time
            weekday = (current_time.weekday() > 5)*1  # 0 if weekday, 1 if weekend
            hour = current_time.hour

            # get time difference between current time and end of hour
            time_diff = min(current_time + datetime.timedelta(hours=1), row["end_time"]) - current_time
            time_diff = time_diff.total_seconds() / 3600

            # Get the price from the reference table
            if price_ref_df is not None:
                price = price_ref_df.iloc[weekday,hour]
            else:
                price = price_ref

            # Add the price to the total
            total_price += price * row["per_hour_kWh"] * time_diff

            # Increment the current time by 1 hour
            current_time += datetime.timedelta(hours=1)

        return total_price


    # --- Calculate resource use for a single row
    def calculate_emissions_row(self, row):

        # Load reference data
        if isinstance(self.carbon_intensity, pd.DataFrame): 
            emissions_ref_df = self.carbon_intensity
        else:
            emissions_ref_df = None
            emissions_ref = self.carbon_intensity

        # Calculate emissions
        total_emissions = 0.0
        current_time = row["start_time"]

        while current_time <= row["end_time"]:
            # Get the month and hour values from the current time
            month = current_time.month - 1
            hour = current_time.hour

            # get time difference between current time and end of hour
            time_diff = min(current_time + datetime.timedelta(hours=1), row["end_time"]) - current_time
            time_diff = time_diff.total_seconds() / 3600

            # Get the emissions from the reference table
            if emissions_ref_df is not None:
                emissions = emissions_ref_df.iloc[month,hour]
            else:
                emissions = emissions_ref

            # Add the emissions to the total
            total_emissions += emissions * row["per_hour_kWh"] * time_diff

            # Increment the current time by 1 hour
            current_time += datetime.timedelta(hours=1)

        return total_emissions



    ## --- Convert emissions figures to more tangable measures
    def calculate_emission_comparisons(self):

        emissions = self.stats_out["total_emissions"]

        # Read reference values from reference file
        with open(self.emission_refs, "r") as file:
            reference_data = yaml.safe_load(file)

        ## Calculate relative emissions
        self.stats_out["rel_washing"]    = round(emissions / reference_data["emissions"]["washing_machine_cycle"]["CO2"], 2)
        self.stats_out["rel_car_1km"]    = round(emissions / reference_data["emissions"]["car_1km"]["CO2"], 2)
        self.stats_out["rel_tree_month"] = round(emissions / reference_data["emissions"]["tree_month"]["CO2"], 2)
        self.stats_out["rel_cph_london"] = round(emissions / reference_data["emissions"]["flight_cph_lon"]["CO2"], 3)

        ## Calculate offsetting prices
        self.stats_out["rel_offset_min"] = round(emissions / 1000000 * reference_data["emissions"]["ton_offset_min"]["CO2"], 2)
        self.stats_out["rel_offset_max"] = round(emissions / 1000000 * reference_data["emissions"]["ton_offset_max"]["CO2"], 2)




## -- Function to print results to screen
def print_output(self, res_dict):

    print("-- Finished calculating resource use --")
    print("")
    print("")

    print("--------------------------------------------------------------------")
    print("----                    REPORT                                  ----")
    print("")
    print(f"      Computation began: {str(res_dict['global_time_start'])}")
    print(f"      Computation ended: {str(res_dict['global_time_end'])}")
    print(f"      total real time spent: {res_dict['global_timespan']} hours")
    print(f"      total cpu time spent: {res_dict['total_cpu_time']} hours")
    print("")
    print(f"      number of 16GB RAM sticks used: {res_dict['ram_sticks_used']}")
    print("")
    print(f"      Estimated energy use:          {res_dict['total_energy_use']} kWh")
    print(f"      Estimated data center cost:    {res_dict['total_dkk']} {self.price_currency}")
    print(f"      Estimated emissions generated: {res_dict['total_emissions']} g CO2")
    print(f"      Price to offset carbon:        {res_dict['rel_offset_min']}-{res_dict['rel_offset_max']} DKK")
    print("")
    print("      The carbon generated from your script corresponds to:")
    print(f"      - running {res_dict['rel_washing']} cycles on a washing mashine")
    print(f"      - driving {res_dict['rel_car_1km']} km in a passenger car")
    print(f"      - {res_dict['rel_tree_month']} months of a tree`s carbon sequestration")
    print(f"      - flying {res_dict['rel_cph_london']} times from CPH to london")
    print("")
    #print(f"     * The price shown here is only for the cost of pure energy.")
    #print(f"       The actual energy price will be higher and then comes the.")
    #print(f"       additional cost of running a datacenter.")
    print("--------------------------------------------------------------------")




## --- Function to parse user input
def parse_args():

    arg_desc = '''\
        Let's calculate your resource use, Yay!
        ---------------------------------------
            This program will look at the PBS
            log or a snakmake logfile and then
            determine the energy use and emissions
            related to running the job(s).
        '''

    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
                                     description = arg_desc)

    parser.add_argument(dest = "user_inputs", nargs='*',
                        help = "Either a list of job IDs or a snakemake logfile. Default input is job IDs.")
    parser.add_argument("-a","--array", action="store_true", default=False,
                        help = "If you want to calculate the resource use for an array of jobs, use this flag. \
                                Instead of passing all the individual job IDs just pass the job array ID.")
    parser.add_argument("-l","--logfile", action="store_true", default=False,
                        help="Flag indicating that input is a snakemake logfile. Default is FALSE.")
    parser.add_argument("-f","--forecast", action="store_true", default=False,
                        help="Flag indicating that you want a emissions forecast. \
                              You will then need input the recources requred by the job using \
                              --walltime, --memory and --cpus. Default is FALSE.")

    forecast = parser.add_argument_group(title='Forecast')
    forecast.add_argument("-t","--walltime", help="Walltime of job in format HH:MM:SS")
    forecast.add_argument("-m","--memory", type = str, help="Memory usage of job in format '###gb'")
    forecast.add_argument("-c","--cpus", type = int, default = 1, help="Number of CPUs used by job")
    forecast.add_argument("-g","--gpus", type = int, default = 0, help="Number of GPUs used by job")


    args = parser.parse_args()

    # Test input
    if args.logfile:
        input_type = "logfile"
        user_input = args.user_inputs
    elif args.forecast:
        input_type = "forecast"
        user_input = [args.walltime, args.memory, args.cpus, args.gpus]
    elif args.array:
        input_type = "jobarray"
        user_input = args.user_inputs
    else:
        input_type = "jobid"
        user_input = args.user_inputs


    ## Catch errors in user input
    if args.forecast and any(arg is None for arg in user_input):
        parser.error("When forecasting emissions you must provide --walltime, --mem_gb, and --cpus / --gpus values.")
    elif (args.walltime or args.memory) and not args.forecast:
        parser.error("When forecasting emissions you must provide the --forecast flag.")
    elif input_type in ["jobid", "jobarray"] and user_input == []:
        parser.error("When calculating emissions you must provide job ID(s).")


    return(user_input, input_type)


## BEGIN
if __name__=="__main__":

    # Parse input
    user_input, input_type = parse_args()

    # Run program
    cd = ScienceFarts(user_input, input_type, config_file = "config.yaml")
    cd.run()

    # Print results
    print_output(cd, cd.stats_out)
