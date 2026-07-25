"""Webcam barcode scanning for ISBN lookup.

Uses OpenCV to capture frames from a webcam and pyzbar to decode EAN-13
barcodes (the standard format ISBNs are printed as on book covers).
Decoding is restricted to EAN-13 codes prefixed 978/979 so an unrelated
barcode drifting into frame doesn't get misreported as the book's ISBN,
and a candidate must be read on two consecutive frames before it's
accepted, to guard against rare misdecodes on blurry frames.

Both libraries are optional — if either is missing, scanner_available()
returns False and the UI should fall back to manual entry.

Install with:
    pip install opencv-python pyzbar
"""

from __future__ import annotations

import sys


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
    on_blur(is_blurry: bool), if given, is called on every frame so the
    UI can prompt the user to hold steady / move back when the image is
    too out-of-focus to decode.
    """

    # Laplacian variance below this is treated as "too blurry to decode".
    # Tuned loosely — sharp, in-focus text/barcodes typically score in the
    # hundreds to thousands; a soft, defocused frame usually falls below 60.
    BLUR_THRESHOLD = 60.0

    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._cap = None
        self._running = False
        self._last_candidate: str | None = None
        self._last_candidate_hits = 0

    def start(self, on_frame, on_found, on_blur=None) -> bool:
        """Start the capture loop. Returns False if the camera can't open."""
        try:
            import cv2
        except ImportError:
            return False

        # OpenCV's default MSMF backend fails to deliver frames on some
        # webcams (opens fine, isOpened() is True, but every read() fails).
        # DirectShow is the reliable backend for UVC devices on Windows.
        if sys.platform == "win32":
            self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self._cap = None
            return False

        # Request a larger capture resolution so the live preview isn't just
        # an upscaled, blurry version of the camera's default (often 640x480
        # or smaller) frame, and so small/distant barcodes have enough
        # pixels for pyzbar to lock onto.
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Make sure continuous autofocus is on — some drivers default to a
        # fixed focus distance until this is set explicitly. Harmless no-op
        # on cameras that don't support the property.
        self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        self._running = True
        self._on_frame = on_frame
        self._on_found = on_found
        self._on_blur = on_blur
        self._cv2 = cv2
        self._last_candidate = None
        self._last_candidate_hits = 0
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

        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        sharpness = self._cv2.Laplacian(gray, self._cv2.CV_64F).var()
        is_blurry = sharpness < self.BLUR_THRESHOLD
        if self._on_blur:
            self._on_blur(is_blurry)

        # Skip the (relatively expensive) barcode search entirely on frames
        # too soft to decode anyway — pyzbar would just fail on them, so
        # this only saves CPU, but it keeps the preview responsive while
        # autofocus hunts for a sharp image.
        isbn = None if is_blurry else self._decode(gray)
        if isbn:
            # Require the same reading twice in a row before accepting it.
            # A single-frame hit is occasionally a motion-blurred misread
            # that still happens to pass the barcode's checksum; requiring
            # a repeat all but eliminates false triggers without adding
            # noticeable delay (frames arrive every ~30ms).
            if isbn == self._last_candidate:
                self._last_candidate_hits += 1
            else:
                self._last_candidate = isbn
                self._last_candidate_hits = 1

            if self._last_candidate_hits >= 2:
                self._running = False
                if self._on_found:
                    self._on_found(isbn)
        else:
            self._last_candidate = None
            self._last_candidate_hits = 0

        return self._running

    def _decode(self, gray) -> str | None:
        """Try to decode an EAN-13 barcode from a grayscale *frame*. Returns the ISBN or None."""
        try:
            from pyzbar import pyzbar
        except ImportError:
            return None

        # Plain grayscale decodes most well-lit, in-focus barcodes. When that
        # fails, retry against a contrast-boosted version — book covers are
        # often glossy or unevenly lit, which flattens the bars enough that
        # pyzbar can't find an edge.
        candidates = [gray, self._cv2.equalizeHist(gray)]

        # Restrict to EAN-13: it's the only symbology ISBN barcodes use, and
        # scanning for every symbology pyzbar supports risks decoding an
        # unrelated barcode (price tag, shelf label, another product in
        # frame) and misreporting it as the book's ISBN.
        symbols = [pyzbar.ZBarSymbol.EAN13]

        for image in candidates:
            barcodes = pyzbar.decode(image, symbols=symbols)
            for barcode in barcodes:
                data = barcode.data.decode("utf-8", errors="ignore").strip()
                if data.isdigit() and len(data) == 13 and data[:3] in ("978", "979"):
                    return data
        return None

    def stop(self) -> None:
        """Release the camera and stop the capture loop."""
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
