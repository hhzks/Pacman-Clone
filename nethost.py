import socket
import threading
import time

from netcommon import encode, decode, ReliableChannel, PacketType


class HostSession:
    """UDP socket + background listener thread. This is the scaffolding —
    higher-level concerns (handshake, lobby, broadcast, disconnects) are
    added in later tasks."""

    def __init__(self, bind_port, bind_host="127.0.0.1"):
        self._bind_port = bind_port
        self._bind_host = bind_host
        self._sock = None
        self._thread = None
        self._running = False
        self._packet_count = 0
        self._packet_count_lock = threading.Lock()
        self._reliable = None  # Constructed in start()

    @property
    def port(self):
        return self._bind_port

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._bind_host, self._bind_port))
        self._sock.settimeout(0.1)
        self._reliable = ReliableChannel(send_callback=self._raw_send)
        self._running = True
        self._thread = threading.Thread(target=self._listener_loop,
                                        name="HostListener", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._sock is not None:
            self._sock.close()
        self._sock = None
        self._thread = None

    def is_running(self):
        return self._running

    def _raw_send(self, addr, packet):
        if self._sock is None:
            return
        try:
            self._sock.sendto(encode(packet), addr)
        except OSError:
            pass  # socket closed during shutdown

    def _listener_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(8192)
            except socket.timeout:
                self._reliable.tick()
                continue
            except OSError:
                return  # socket closed
            packet = decode(data)
            if packet is None:
                continue
            with self._packet_count_lock:
                self._packet_count += 1
            # Further handling (handshake, input dispatch) added in later tasks.
            self._reliable.handle_incoming(addr, packet)

    def debug_packet_count(self):
        with self._packet_count_lock:
            return self._packet_count
