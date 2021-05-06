#!/bin/sh

set -e

cd $ZOTSYNCFOLDER_HOME
npm install zotero
npm install configparser
node zotero_notifier.js
