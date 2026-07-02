"""Webcam barcode scanning for ISBN lookup.

Uses OpenCV to capture frames from a webcam and pyzbar to decode
barcodes (EAN-13 is the standard ISBN barcode format).

Both libraries are optional — if either is missing, scan_for_isbn()
returns None immediately and the UI should fall back to manual entry.

Install with:
    pip install opencv-python pyzbar
"""

from __future__ import annotations


def scanner_available() -> bool:
    """Return True if both opencv-python and pyzbar are importable."""
    try:
        import cv2          # noqa: F401
        from pyzbar import pyzbar  # noqa: F401
        return True
    except ImportError:
        return False


class BarcodeScanner:
    """Wraps a webcam capture loop that watches for an EAN-13 barcode.

    Usage:
        scanner = BarcodeScanner()
        scanner.start(on_frame=callback, on_found=found_callback)
        ...
        scanner.stop()

    on_frame(frame) is called for every captured frame (as a numpy array,
    suitable for converting to a PhotoImage for live preview).
    on_found(isbn: str) is called once when a barcode is successfully
    decoded; the scanner stops itself automatically after a hit.
    """

    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._cap = None
        self._running = False

    def start(self, on_frame, on_found) -> bool:
        """Start the capture loop. Returns False if the camera can't open."""
        try:
            import cv2
        except ImportError:
            return False

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self._cap = None
            return False

        self._running = True
        self._on_frame = on_frame
        self._on_found = on_found
        self._cv2 = cv2
        return True

    def poll(self) -> bool:
        """Capture and process a single frame. Returns False when stopped.

        Call this repeatedly from a Tkinter `after()` loop — never block
        the main thread with a tight while-loop.
        """
        if not self._running or self._cap is None:
            return False

        ret, frame = self._cap.read()
        if not ret:
            return self._running

        if self._on_frame:
            self._on_frame(frame)

        isbn = self._decode(frame)
        if isbn:
            self._running = False
            if self._on_found:
                self._on_found(isbn)

        return self._running

    def _decode(self, frame) -> str | None:
        """Try to decode an EAN-13 barcode from *frame*. Returns the ISBN or None."""
        try:
            from pyzbar import pyzbar
        except ImportError:
            return None

        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)
        for barcode in barcodes:
            data = barcode.data.decode("utf-8", errors="ignore").strip()
            # ISBN-13 barcodes start with 978 or 979 and are 13 digits
            if data.isdigit() and len(data) == 13 and data[:3] in ("978", "979"):
                return data
            # Some barcodes encode ISBN-10 directly
            if len(data) == 10:
                return data
        return None

    def stop(self) -> None:
        """Release the camera and stop the capture loop."""
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
