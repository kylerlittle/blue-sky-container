#!/bin/bash

#PBS -V

#PBS -N parallel_sort_klitte

## Define compute options
#PBS -l nodes=1:dev:amd:ppn=4
  ##PBS -l nodes=1:dev:intel:ppn=4
#PBS -l mem=100mb
#PBS -l walltime=00:02:00
#PBS -q batch

## Define path for output & error logs
#PBS -k o
  ##PBS -j oe
#PBS -e /fastscratch/klitte/parallel_sort_klitte.e
#PBS -o /fastscratch/klitte/parallel_sort_klitte.o

## Define path for reporting
#PBS -M kyler.little@wsu.edu
#PBS -m abe

# Start from directory where job was submitted from
cd $PBS_O_WORKDIR

# Init singularity modules
./singularity_init.sh

# Run container
singularity exec containers/class-work_ubuntu_cpp.sif ./parallel-sorting/p_merge_sort.sh