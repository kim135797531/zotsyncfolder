#!/bin/sh

set -e
date
TZ=Asia/Seoul
date

cd $ZOTSYNCFOLDER_HOME
/opt/conda/bin/conda run -n $CONDA_ENV_NAME sh -c 'python construct_folder.py > /dev/tty 2>&1'
