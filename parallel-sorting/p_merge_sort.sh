#!/bin/bash

# Get script directory absolute path. This way script always runs as if from within 'scripts/' dir.
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
cd "$scriptDir"

g++ -pthread parallel_merge_sort.cpp -o parallel-sorting-code && ./parallel-sorting-code

