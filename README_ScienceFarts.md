# ScienceFarts - Calculate the resource use and emissions of your jobs

Author: Alexander Pil Henriksen

Created: July 2022 - Updated continously

## How to use it

ScienceFarts is a small script I have written for you to evaluate the energy use and co2 emissions of your job/script. It can also be used by the end of a snakemake pipeline.
There are two different cases in which you can use ScienceFarts:

1.  You want to check the emissions of a job with a known job ID.
2.  You want to check the emissions of a snakemake pipeline that you are running.
3.  You want to check the estimated emissions of a future job.

**NB:** ScienceFarts uses `python3` so make sure to have that loaded before using ScienceFarts. It will NOT work with `python2`.

### Known job ID

If you want to check the emissions of a job with a known job ID simply run the following block of code:

```
python /data/code_base/script_emissions/ScienceFarts.py <job_id>
```

You can also check the emissions of a list of jobs all contained in a job array. For that you can use the `--array` flag.

```
python /data/code_base/script_emissions/ScienceFarts.py --array <job_array_id>
```

### snakemake pipeline

If you want to check the emissions of a snakemake pipeline all you have to do to use it is to add the following lines to the end of your snakefile:

```
# When the pipeline has finished, calculate resource use
onsuccess:
	print("-- Pipeline successfull. Calculating resource use. --")
	shell("python /data/code_base/script_emissions/ScienceFarts.py {log} --logfile")
```

Of course, you may also want to calculate the resource use of runs that fail. To also compute those simply also add the lines below.

```
# If the pipeline has crashed, calculate resource use
onerror:
	print("-- Pipeline crashed :-( Calculating resource use. --")
	shell("python /data/code_base/script_emissions/ScienceFarts.py {log} --logfile")
```

This means that to use ScienceFarts, it is not necessary to pull this repository. It is simply here to save the code. All the code you need is stored in `/data/code_base/script_emissions/` and you can simply copy the lines shown above if you wish to use ScienceFarts.

### Future job

If you want to estimate the emissions of a future job that you may run, you can also check this using ScienceFarts.
You will need to have an estimate of 3 metrics:

*   The walltime the job will consume
*   The number of CPUs necessary
*   The amount of memory that will be used
*	Additionally, you can define the number of GPUs necessary

Given you have estimates of these 3 (or 4) metrics you can estimate the emissions of your job using the following syntax:

```
python /data/code_base/script_emissions/ScienceFarts.py --forecast --walltime <HH:MM:SS> --memmory <Xgb> --cpus <integer> --gpus <integer>
```

As is shown from the above code, you need to use the `--forecast` flag and input the three metrics with their respective flags. `walltime` should be in format `HH:MM:SS`, similar to when you use the queing system through `qsub`. GPUs and CPUs should simpy be input as numbers, while memory should be written as "16gb" for 16 GB or "400mb" for 400 MB and so on.

The output will be in the same format as when calculating emissions for a job that has actually run. Also, ScienceFarts will assume that the job is being run immediately and so the energy and emission calculations will be based on a job that was running from when you ran ScienceFarts and onwards for a time corresponding to `walltime`.


## How it works

The script is very simple. What it does is basically this:

1.	Evaluate whether you have provided a logfile (as in the snakemake case) or a list of job IDs
2.  If a logfile has been provided then read throug the logfile and extract job IDs.
3.  Fetch the logs for those job IDs and then extract information on start/end time as well as cpu time and cores used.
4.	Use the formula `(time_end - time_start) * cores * pr_core_energy_use + (time_end - time_start) * GPUs * pr_gpu_energy_use` to calculate the energy use. Here, I have assumed a energy use per core of 15 W and a per GPU use of 400 W.
5.	Look up the co2 emissions per kWh in a table built with data from [energidataportal.dk](www.energidataportal.dk).
6.	Convert the emissions to more identifiable units such as cycles on a washing machine or kms in a car.
7.	Print report


Most of the steps above probably don't need further explanations except for step 5, the conversion from energy units to co2 emission units. To make the conversion I downloaded a year's worth of energy emissions data from [energidataportal.dk](www.energidataportal.dk), the data service of EnergiNet - an organization within the Danish Ministry of Climate, Energy and Utilities. Here they have data on energy emissions every 5 minutes starting from 2017. Since the relative emissions of energy use are falling as more renewable energy is being installed I have chosen only to use the emissions data from the last year (March 2021 - February 2022).

What I have then done is calculate averages of each hour of every month meaning that for each month I calculate 24 values: 00 o-clock, 01 o-clock, 02 o-clock and so on. This is assuming that the biggest differences in emissions are between different times of the day as well as different times of the year. In the end this leaves me with a table of 24x12 cells representing the mean co2 emission per kWh for each clock-hour of every month.

When calculating the emissions of a finished snakemake pipeline the start and end times are used to create a matrix of "hours" in which the pipeline was running. So for example if a pipeline ran for 48 hours from May 12th 12:00 to May 14th 12:00 the matrix would show 2 hours in "May 12:00", 2 hours in "May 13:00" and so on. This matrix is then multiplied with the mounth-hour emissions data to generate the final figure.

## Inspiration

This little "module" is partly inspired by [green-algorithms](www.green-algorithms.org), a project by L. Lannelongue, J. Grealey and M. Inouye. You can see their work in their paper on the algorithm[^1] and some other thoughts on green computing in another paper of theirs[^2].

[^1]: Lannelongue, L., Grealey, J., Inouye, M., Green Algorithms: Quantifying the Carbon Footprint of Computation. Adv. Sci. 2021, 2100707. https://doi.org/10.1002/advs.202100707
[^2]: Lannelongue L, Grealey J, Bateman A, Inouye M. Ten simple rules to make your computing more environmentally sustainable. PLoS Comput Biol. 2021 Sep 20;17(9):e1009324. doi: 10.1371/journal.pcbi.1009324


## Questions, comments

If you have any questions, comments or suggestions for the improvement of this tool, please feel free to contact me at alexander.henriksen@cpr.ku.dk.
