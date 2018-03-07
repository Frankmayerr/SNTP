import socket
import struct
import time

TIME1970 = 2208988800
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
data = b'\x1b' + 47 * b'\0'
while (True):
    client.sendto(data, (b'localhost', 123))
    data, address = client.recvfrom(1024)
    if data:
        print('Response received from:', address)
        t = struct.unpack('!12I', data)[10]
        t -= TIME1970
        print('\tTime=%s' % time.ctime(t))
    time.sleep(5)

# t = ((T2 - T1) + (T3 - T4)) / 2.
