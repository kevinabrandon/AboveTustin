#!/bin/bash
#
# This is just a simple script that loads the correct python enviroment
# and then loops forever restarting the tracker program if it ever exits.
#

cd /home/pi/AboveTustin
source py3/bin/activate


while :
do
	echo
	echo '***** Restarting AboveTustin ' `date --utc --rfc-3339=ns`
	echo

	python3 tracker.py

	echo
	echo '***** AboveTustin exited ' `date --utc --rfc-3339=ns`
	echo

	sleep 5

done

