import socket
import pytest


@pytest.fixture
def free_udp_port():
    """Bind to port 0 on localhost, grab the assigned port, release the socket."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
