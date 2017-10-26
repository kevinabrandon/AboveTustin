#
# fa_api.py
#
# Sergiusz Paprzycki <serek@walcz.net>
# 

import requests

def FlightInfo(ident, username, apiKey, verbose=0, results=10):
	fxmlUrl = "https://flightxml.flightaware.com/json/FlightXML3/"
	ident = ident.strip()
	payload = {'ident':ident, 'howMany':results}
	response = requests.get(fxmlUrl + "FlightInfoStatus", params=payload, auth=(username, apiKey))
	output = dict()
	if response.status_code == 200:
		decodedResponse = response.json()
		for flight in decodedResponse['FlightInfoStatusResult']['flights']:
			if flight['status'] == 'On' or flight['status'] == 'En':
				output = {
					"orig_name":flight['origin']['airport_name'],
					"orig_alt":flight['origin']['alternate_ident'],
					"orig_code":flight['origin']['code'],
					"dest_name":flight['destination']['airport_name'],
					"dest_alt":flight['destination']['alternate_ident'],
					"dest_code":flight['destination']['code']
				}
				break
		if verbose:
			return decodedResponse
		else:
			return output
	else:
		return False

