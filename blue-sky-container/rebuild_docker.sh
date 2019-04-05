#!/bin/bash

IM_NAME=blueskycontainer
DOCKER_IMAGE="kylerlittle/broken-tooth:${IM_NAME}"

# Rebuild image
docker build . -t $IM_NAME

# Tag and share to DockerHub
docker tag $IM_NAME $DOCKER_IMAGE
docker push $DOCKER_IMAGE
