 # TorqueDork

Author: Alexander Pil Henriksen

Created: April 2023 - Updated continously

## TLDR

Step 1: Run scrapeTorque.py `python scrapeTorque.py`

Step 2: Type `python torqueDork.py` in the commandline. 

Step 3: Such cool, much wow

## What is TorqueDork?

`TorqueDork` is a small python module and function that can be used to see how efficiently you use the resources you reserve in the Torque queing system. 

In short, `TorqueDork`does 3 things:
1. It queries a `sqlite3` database that holds all the records for every submitted job.
2. It uses the queried records to calculate efficiency for the last 30 days.
3. It prints the results to the screen

The results that are printed to the screen are in the form of bar charts showing how the different users perform compared to eachother. Top users (with the best score) are shown at the top.

## What metrics does `TorqueDork` compute?

`TorqueDork` computes 4 metrics that are printed to the screen.

1. Memory efficiency - Used memory / reserved memory
2. CPU time efficiency - Used CPU time / reserved CPU time  (reserved CPU time is the spent walltime * nr of cores)
3. Memory waste - Reserved memory - used memory, measured in GB hours
4. Carbon load - Estimated carbon footprint resulting from the jobs of that user. (Using `ScienceFarts`)

## Flags

There are several flags which you can use to customize the `TorqueDork` call.
- `-p, --period`        Lets you specify the number of days into the past you want to query records.
- `-c, --no_carbon`     Flag for NOT computing the carbon load. Default is to compute it.
- `-u, --user`          Specify a user and provide only a small report for that user, instead of the default bar charts.
- `-d, --database`      Specify the path to the `sqlite3` database that holds the records. Default is `./torque_logs.db`

## How to set up `TorqueDork`

### Step 1: Clone the repository

Clone the repository to your local machine.

### Step 2: Install dependencies

Install the dependencies listed in the `requirements.txt` file. You can do this by running the following command in the terminal:

`pip install -r requirements.txt`

### Step 3: Set up the scraper

TorqueDork uses a script to scrape the Torque logs. This script is called `scrapeTorque.py`. Shortly, this script will read the Torque log files and store the results in a `sqlite3` database.
Run the scraper by typing `python scrapeTorque.py` in the commandline. This will create a `sqlite3` database at the path which you provided with the `--log_db` flag. If you did not provide a path, the database will be created in the same folder as the scraper.

**NB** You probably want to avoid having to run the scraper manually every time you want to use `TorqueDork`. To avoid this, you can set up a cron job that runs the scraper at a regular interval. This way, you will always have an updated database with all the records. To do so you can run `crontab -e` in the terminal and add a line like this:

`0 0 * * * /path/to/python /path/to/scrapeTorque.py`

### Step 4: Update the config file

You will need to update the `config.yaml` before you can use `TorqueDork`. In the config file you can specify your specific location, hardware and other settings. This is necessary in order to determine the energy use and the emissions related to the jobs. There are a number of default values you can use. These are contained in reference files in the `reference_data\` folder. See the `config.yaml` file for more information.
For users in Denmark, there are an additional set of files that will allow users to calculate their emissions very precisely. See more in the `README_ScienceFarts.md` file.

### Step 5: Enjoy your fresh new tool

Now that you have a database with all the records, you can run `TorqueDork`. This is done by typing `python torqueDork.py` in the commandline. This will print a report to the screen. If you want to customize the report, you can use the flags described above.

## ScienceFarts

`ScienceFarts` is a small script built for use with `TorqueDork`. It is a small script that estimates the carbon footprint of a finished job. It can also be used to calculate the cumulative footprint from a `snakemake`log file or to estimate the carbon footprint of a future job, given the resources it will use. You can read more about `ScienceFarts` in the `README_ScienceFarts.md` file.