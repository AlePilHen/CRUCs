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

### Step 3: Run the scraper

TorqueDork uses a scraper to scrape the Torque database. This scraper is called `scrapeTorque.py`. Shortly, this scraper will query the Torque database and store the results in a `sqlite3` database.
Run the scraper by typing `python scrapeTorque.py` in the commandline. This will create a `sqlite3` database at the path which you provided with the `--log_db` flag. If you did not provide a path, the database will be created in the same folder as the scraper.

### Step 4: Enjoy your fresh results

Now that you have a database with all the records, you can run `TorqueDork`. This is done by typing `python torqueDork.py` in the commandline. This will print a report to the screen. If you want to customize the report, you can use the flags described above.

## ScienceFarts

`ScienceFarts` is a another small script that I build for use with `TorqueDork`. It is a small script that estimates the carbon footprint of a job. It can also be used to calculate the cumulative footprint from a `snakemake`log file or to estimate the carbon footprint of a future job, given the resources it will use. You can read more about `ScienceFarts` in the `README_ScienceFarts.md` file.