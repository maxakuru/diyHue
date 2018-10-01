#!/bin/bash
mac=`cat /sys/class/net/$(ip route get 8.8.8.8 | sed -n 's/.* dev \([^ ]*\).*/\1/p')/address`
arch=`uname -m`

curl https://raw.githubusercontent.com/mariusmotea/diyHue/9ceed19b4211aa85a90fac9ea6d45cfeb746c9dd/BridgeEmulator/openssl.conf -o openssl.conf
serial="${mac:0:2}${mac:3:2}${mac:6:2}fffe${mac:9:2}${mac:12:2}${mac:15:2}"
dec_serial=`python3 -c "print(int(\"$serial\", 16))"`
openssl req -new  -config openssl.conf  -nodes -x509 -newkey  ec -pkeyopt ec_paramgen_curve:P-256 -pkeyopt ec_param_enc:named_curve   -subj "/C=NL/O=Philips Hue/CN=$serial" -keyout private.key -out public.crt -set_serial $dec_serial
if [ $? -ne 0 ] ; then
	echo -e "\033[31m ERROR!! Local certificate generation failed! Attempting remote server generation\033[0m"
	### test is server for certificate generation is reachable
	if ! nc -z mariusmotea.go.ro 9002 2>/dev/null; then
		echo -e "\033[31m ERROR!! Certificate generation service is down. Please try again later.\033[0m"
		exit 1
	fi
	curl "http://mariusmotea.go.ro:9002/gencert?mac=$mac" > ~/.diyhue/cert.pem
else
	touch ~/.diyhue/cert.pem
	cat private.key >> ~/.diyhue/cert.pem
	cat public.crt >> ~/.diyhue/cert.pem
	rm private.key public.crt
fi
