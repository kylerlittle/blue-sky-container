#!/bin/bash

# TODO > this is way too many copies... do less.

echo "In the get_blue_sky_files.sh script..."

export AEOLUSHPCC=aeolus.wsu.edu
export BSUSER=klitte

# SSH into Aeolus, then secure copy blue-sky-files into home/$BSUSER/$TEMP_BS/ dir.
ssh "${BSUSER}@${AEOLUSHPCC}" 'bash -s' << 'ENDSSH'
    echo "Hello ${USER}. You are inside $(hostname)!"
    export bluenode=10.1.1.28
    mkdir -p bluesky_3.5.1
    scp -r "${bluenode}:/opt/bluesky/bluesky_3.5.1/" "./"
ENDSSH

# Copy remote blue-sky-files on Aeolus to local dir
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/bluesky_3.5.1/" ./

echo "... finished get_blue_sky_files.sh script"
