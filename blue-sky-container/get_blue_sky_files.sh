#!/bin/bash

# TODO > this is way too many copies... do less.

echo "In the get_blue_sky_files.sh script..."

export AEOLUSHPCC=aeolus.wsu.edu
export BSUSER=klitte

# SSH into Aeolus, then secure copy blue-sky-files into home/$BSUSER/$TEMP_BS/ dir.
ssh "${BSUSER}@${AEOLUSHPCC}" 'bash -s' << 'ENDSSH'
    echo "Hello ${USER}. You are inside $(hostname)!"
    export bluenode=10.1.1.28
    export TEMP_BS=temp_bs
    mkdir -p "${TEMP_BS}"
    scp "${bluenode}:/opt/bluesky/bluesky_3.5.1/bluesky" "./${TEMP_BS}/"
    scp "${bluenode}:/opt/bluesky/bluesky_3.5.1/BSF_EFO_AP5_SFonly.csh" "./${TEMP_BS}/"
    scp -r "${bluenode}:/opt/bluesky/bluesky_3.5.1/base/" "./${TEMP_BS}/"
    scp -r "${bluenode}:/opt/bluesky/bluesky_3.5.1/input/" "./${TEMP_BS}/"
    scp -r "${bluenode}:/opt/bluesky/bluesky_3.5.1/modules/" "./${TEMP_BS}/"
    scp -r "${bluenode}:/opt/bluesky/bluesky_3.5.1/setup/" "./${TEMP_BS}/"
ENDSSH

# Copy remote blue-sky-files on Aeolus (in $TEMP_BS) to local dir
export BS_FILES_DIR=blue-sky-files
export TEMP_BS=temp_bs
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/${TEMP_BS}/bluesky" "./${BS_FILES_DIR}"
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/${TEMP_BS}/BSF_EFO_AP5_SFonly.csh" "./${BS_FILES_DIR}"
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/${TEMP_BS}/base/" "./${BS_FILES_DIR}"
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/${TEMP_BS}/input/" "./${BS_FILES_DIR}"
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/${TEMP_BS}/modules/" "./${BS_FILES_DIR}"
scp -r "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/${TEMP_BS}/setup/" "./${BS_FILES_DIR}"

echo "... finished get_blue_sky_files.sh script"
