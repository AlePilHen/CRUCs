 # TorqueDork

Author: Alexander Pil Henriksen

Created: April 2023 - Updated continously

## TLDR

Step 1: Type `python torqueDork` in the commandline. 

Step 2: Such cool, much wow

## What is TorqueDork?

`TorqueDork` is a small python module and function that can be used to see how efficiently you use the resources you reserve in the Torque queing system. 

In short, `TorqueDork`does 3 things:
1. It queries a `sqlite3` database that holds all the records for every submitted job.
2. It uses the queried records to calculate efficiency for the last 30 days.
3. It prints the results to the screen

The results that are printed to the screen are in the form of bar charts showing how the different users perform compared to eachother. Top users (with the best score) are shown at the top.

## What metrics does `TorqueDork`compute?

`TorqueDork` computes 3 metrics that are printed to the screen.

1. Memory efficiency - Used memory / reserved memory
2. CPU time efficiency - Used CPU time / reserved CPU time  (reserved CPU time is the spent walltime * nr of cores)
3. Carbon load - Estimated carbon footprint resulting from the jobs of that user.

## Flags

There are several flags which you can use to customize the `TorqueDork` call.
- `-p, --period`        Lets you specify the number of days into the past you want to query records.
- `-c, --no_carbon`     Flag for NOT computing the carbon load. Default is to compute it.
- `-u, --user`          Specify a user and provide only a small report for that user, instead of the default bar charts.