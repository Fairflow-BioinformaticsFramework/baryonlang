#!/usr/bin/env bash

docker run -it --rm   -v /var/run/docker.sock:/var/run/docker.sock   -v $(pwd):$(pwd)   -v /home/baseolo/Baryon_SourceCode:/home/baseolo/Baryon_SourceCode   -w $(pwd)   -e DOCKER_API_VERSION=1.44   nextflow/nextflow:26.04.6 nextflow run topx.nf
