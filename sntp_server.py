import queue
import socket
import struct
import sys
import threading
import time

import select


class SNTPData:
    time1970 = 2208988800

    def __init__(self, delay=0, stratum=2, version=4, mode=3, original_time=0, recv_time=0):
        self.LI = 0  # 2b leap(correction) indicator
        self.VN = version  # 3b version
        self.mode = mode  # 3b
        self.stratum = stratum  # 8b only for server (OFS): sync
        self.poll = 0  # 8b (OFS) max interval between two messages
        self.precision = 0  # 8b prec of system time
        self.root_delay = 0  # 32b time from send and recv to time server
        self.root_dispersion = 0  # (OFS) 32b max error due to instability
        self.ref_id = 0  # 32b
        # for 0,1 stratum - the synchronization source server
        # for secondary server - IP
        self.ref_timestamp = 0  # 64b last time when time was sync-ed
        self.orig_timestamp = original_time  # 64b client sending time
        self.recv_timestamp = recv_time  # 64b receiving time by server
        self.transmit_timestamp = 0  # 64b server sending time
        self.delay = delay
# kerbers AD
    def make_data(self):
        def bin_with_zero_add(num, leng):
            return bin(num)[2:].rjust(leng, '0')

        first_in_binary = bin_with_zero_add(self.LI, 2) + bin_with_zero_add(self.VN, 3) + \
                          bin_with_zero_add(self.mode, 3)
        first_byte = int(first_in_binary, 2)
        self.ref_timestamp = self.parse_time(self.get_time_with_delay())
        self.transmit_timestamp = self.get_time_with_delay()
        packet = struct.pack('!4B3L2LQ4L', first_byte, self.stratum, self.poll, self.precision, self.root_delay,
                             self.root_dispersion, self.ref_id, *self.ref_timestamp, self.orig_timestamp,
                             *(self.parse_time(self.recv_timestamp) + self.parse_time(self.transmit_timestamp)))
        return packet

    def get_time_with_delay(self):
        return time.time() + self.delay

    @staticmethod
    def parse_time(ttime):
        sec, mill_sec = str(ttime + SNTPData.time1970).split('.')
        mill_sec = float('0.{}'.format(mill_sec)) * 2 ** 32
        return int(sec), int(mill_sec)

    def parse_data(self, data):
        def get_first_byte(num):
            num = bin(num)[2:].rjust(8, '0')
            lp = int(num[:2], 2)
            ver = int(num[2:5], 2)
            mode = int(num[5:], 2)
            return lp, ver, mode

        try:
            unpacked = struct.unpack('!4B3L4Q', data[0:struct.calcsize('!4B3L4Q')])
            self.LI, self.VN, self.mode = get_first_byte(unpacked[0])
            self.transmit_timestamp = struct.unpack('!Q', data[40:48])[0]
        except struct.error:
            print('Invalid SNTP format', file=sys.stderr)


class SNTPProtocol:
    def __init__(self, sock, delay=0):
        self.sock = sock
        self.delay = delay
        self.tasks = queue.Queue()
        self.sock.settimeout(5)

    def receiving(self):
        while True:
            rlist, wlist, elist = select.select([self.sock], [], [], 5)
            if rlist:
                for curSock in rlist:
                    data, addr = curSock.recvfrom(1024)
                    print('Connected: ', addr[0])
                    self.tasks.put((data, addr, time.time()))

    def make_request(self):
        while True:
            try:
                data, addr, recv_time = self.tasks.get(timeout=1)
                client_packet = SNTPData()
                client_packet.parse_data(data)
                server_packet = SNTPData(self.delay, stratum=3, version=client_packet.VN, mode=4,
                                         original_time=client_packet.transmit_timestamp,
                                         recv_time=recv_time + self.delay)
                self.sock.sendto(server_packet.make_data(), addr)
            except queue.Empty:
                continue


def main(delay):
    ip = 'localhost'
    port = 123
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, port))
        sock.settimeout(3)
    except socket.error:
        print('ERROR!', file=sys.stderr)
        sys.exit(-1)
    print('Start', file=sys.stdout)
    sntp = SNTPProtocol(sock, delay)
    recv_th = threading.Thread(target=sntp.receiving)
    recv_th.start()
    req_thread = threading.Thread(target=sntp.make_request)
    req_thread.start()


if __name__ == '__main__':
    delay = sys.argv
    if len(delay) == 1:
        delay.append(3600)
    main(int(delay[1]))
