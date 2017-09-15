#!/bin/bash

pluginname="plugin.video.turbik.tv"
author="gruzzin@gmail.com"

usage() {
    echo "turbik.tv plugin release script"
    echo "Usage: make_release.sh <directory> <version>"
}

if [ $# -ne 2 ]
then
    usage
    exit
fi

releasedir=$1/$pluginname
version_str="<addon id=\"$pluginname\" name=\"turbik.tv\" version=\"$2\" provider-name=\"$author\">"

if [ ! -d $releasedir ]
then
    mkdir -p $releasedir
fi
cp -r $pluginname.devel/* $releasedir/

sed -e "s/^<addon\ i.*/$version_str/" $pluginname.devel/addon.xml > $releasedir/addon.xml
sed -e "s/tv\.devel/tv/" $pluginname.devel/turbik.py > $releasedir/turbik.py

exit
