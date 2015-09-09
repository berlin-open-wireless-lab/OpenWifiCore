#!/bin/sh

wget -q -O- \
    --header='Content-Type: applicantion/json' \
    --post-data="{
				\"params\":
					{\"uuid\":\"12345\",
						\"name\": \"testdf\",
						\"address\": \"127.0.0.1\",
						\"distribution\": \"wgets\",
						\"version\": \"1.0\",
						\"proto\": \"0.1\",
						\"login\": \"foo\",
						\"password\": \"foo\" },
					\"method\": \"device_register\",
					\"jsonrpc\": \"2.0\",
					\"id\": \"8b853e33-cba8-4ccc-8f10-530a0c7b494e\"}" \
    http://localhost:6543/api
