#!/bin/sh

set -e

cd $ZOTSYNCFOLDER_HOME
/opt/conda/bin/conda run -n $CONDA_ENV_NAME python construct_folder.py
