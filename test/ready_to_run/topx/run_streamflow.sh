#!/usr/bin/env bash

docker run --rm -it -v /var/run/docker.sock:/var/run/docker.sock -v $(which docker):/usr/bin/docker -v "$(pwd):/workflow" -v /home/baseolo/Baryon_SourceCode:/home/baseolo/Baryon_SourceCode -w /workflow alphaunito/streamflow streamflow run topx.yml
