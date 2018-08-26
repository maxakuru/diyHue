def get_ip():
	import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]

def get_mac():
	from subprocess import check_output
	cmd = "cat /sys/class/net/$(ip -o addr | "+
			"grep {} | awk '{print $2}')/address".format(get_ip())
	mac = check_output(cmd, shell=True).decode('utf-8').replace(":","")[:-1]
	return mac