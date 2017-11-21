#
# fa_api.py
#
# Sergiusz Paprzycki <serek@walcz.net>
# 

import traceback

import requests

def FlightInfo(ident, username, apiKey, verbose=0, results=10):
	try:
		fxmlUrl = "https://flightxml.flightaware.com/json/FlightXML3/"
		ident = ident.strip()
		payload = {'ident':ident, 'howMany':results}
		response = requests.get(fxmlUrl + "FlightInfoStatus", params=payload, auth=(username, apiKey))
		output = dict()
		if response.status_code == 402:
			print(response.text)
			return False
		if response.status_code == 200:
			decodedResponse = response.json()
			print(decodedResponse)
			if 'FlightInfoStatusResult' not in decodedResponse:
				return False
			for flight in decodedResponse['FlightInfoStatusResult']['flights']:
				if 'status' not in flight:
					continue
				if flight['status'].startswith('On') or flight['status'].startswith('En') or flight['status'].startswith('In'):
					output = {
						"orig_name":flight['origin']['airport_name'],
						"orig_city":flight['origin']['city'],
						"orig_alt":flight['origin']['alternate_ident'],
						"orig_code":flight['origin']['code'],
						"dest_name":flight['destination']['airport_name'],
						"dest_city":flight['destination']['city'],
						"dest_alt":flight['destination']['alternate_ident'],
						"dest_code":flight['destination']['code']
					}
					break
			if verbose:
				return decodedResponse
			else:
				return output
		else:
			print("status code: " % response.status_code)
			print(response.text)
			return False
	except Exception:
		print("exception in fa_api.FlightInfo():")
		traceback.print_exc()
		return False
