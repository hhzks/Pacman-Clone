import threading


class UpnpMapper:
    """Best-effort UPnP port mapping for the host. Discovery + mapping run on
    a background thread; the UI polls .status and .external_ip each frame.

    Status transitions:
        idle -> discovering -> {mapped, unavailable}
    """

    STATUS_IDLE = "idle"
    STATUS_DISCOVERING = "discovering"
    STATUS_MAPPED = "mapped"
    STATUS_UNAVAILABLE = "unavailable"

    def __init__(self, port, description="Pacman Clone"):
        self._port = int(port)
        self._description = description
        self._lock = threading.Lock()
        self._thread = None
        self._upnp = None
        self.status = self.STATUS_IDLE
        self.external_ip = None
        self.error = None

    def start(self):
        with self._lock:
            if self._thread is not None:
                return
            self.status = self.STATUS_DISCOVERING
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="UpnpMapper")
        self._thread.start()

    def _run(self):
        try:
            import miniupnpc
        except ImportError:
            with self._lock:
                self.status = self.STATUS_UNAVAILABLE
                self.error = "miniupnpc not installed"
            return
        try:
            u = miniupnpc.UPnP()
            u.discoverdelay = 2000
            found = u.discover()
            if not found:
                with self._lock:
                    self.status = self.STATUS_UNAVAILABLE
                    self.error = "no UPnP router found"
                return
            u.selectigd()
            ext_ip = u.externalipaddress()
            ok = u.addportmapping(self._port, "UDP", u.lanaddr, self._port,
                                  self._description, "")
            if not ok:
                with self._lock:
                    self.status = self.STATUS_UNAVAILABLE
                    self.error = "router rejected mapping"
                return
            with self._lock:
                self._upnp = u
                self.external_ip = ext_ip
                self.status = self.STATUS_MAPPED
        except Exception as exc:
            with self._lock:
                self.status = self.STATUS_UNAVAILABLE
                self.error = str(exc) or exc.__class__.__name__

    def stop(self):
        """Best-effort unmap. Safe to call whether or not mapping succeeded."""
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        with self._lock:
            u = self._upnp
            port = self._port
            self._upnp = None
        if u is None:
            return
        try:
            u.deleteportmapping(port, "UDP")
        except Exception:
            pass

    def status_line(self):
        """One-line human-readable summary for the lobby UI."""
        with self._lock:
            status = self.status
            ext = self.external_ip
            err = self.error
            port = self._port
        if status == self.STATUS_MAPPED:
            return f"Online: ready  (public {ext}:{port})"
        if status == self.STATUS_DISCOVERING:
            return "Online: setting up (UPnP)..."
        if status == self.STATUS_UNAVAILABLE:
            return f"Online: forward UDP port {port} manually ({err})"
        return ""
