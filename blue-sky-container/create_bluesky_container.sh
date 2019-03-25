echo "In the create_bluesky_container.sh script..."

export AEOLUSHPCC=aeolus.wsu.edu
export BSUSER=klitte

ssh "${BSUSER}@${AEOLUSHPCC}" 'bash -s' << 'ENDSSH'
    echo "Hello ${USER}. You are inside $(hostname)!"
    export bluenode=10.1.1.28
    scp "${bluenode}:/opt/bluesky/bluesky_3.5.1/BSF_EFO_AP5_SFonly.csh" .
ENDSSH

# TODO > Run mkdir -p for every line in 'blue-sky-required-dirs'
mkdir -p /opt/bluesky/bluesky_3.5.1/

# TODO > Run scp for each file in 'blue-sky-required-files'
scp "${BSUSER}@${AEOLUSHPCC}:/home/${BSUSER}/BSF_EFO_AP5_SFonly.csh" /opt/bluesky/bluesky_3.5.1/


echo "... finished create_bluesky_container.sh script"

# Simply run bash now if we want to do anything else.
/bin/bash
