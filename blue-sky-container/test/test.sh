#!/bin/bash

# Compare files in dir1 and dir2 and ensure equality

if [ "$#" -ne 2 ]; then
   echo 'Invalid argument(s).'; \
   echo "Usage $0 <dir1> <dir2>"
else
    if [ -d $1 -a -d $2 ]; then
        #cd $1; \
        for f1 in $(ls $1);
        do
            for f2 in $(ls $2);
            do
                if [ $f1 == $f2 ]; then
                    echo "Comparing $1$f1 $2$f2"; \
                    diff -c "$1$f1" "$2$f2"
                fi
            done
        done
    else
        echo "$1 and $2 must be directories"
    fi
fi
