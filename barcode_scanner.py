"""Webcam barcode scanning for ISBN lookup.

Uses OpenCV to capture frames from a webcam and decodes EAN-13 barcodes
(the standard format ISBNs are printed as on book covers) with zxing-cpp
first, falling back to pyzbar if zxing-cpp isn't installed or comes up
empty — the two use different algorithms and each occasionally succeeds
where the other doesn't. Decoding is restricted to EAN-13 codes prefixed
978/979 so an unrelated barcode drifting into frame doesn't get
misreported as the book's ISBN, and a candidate must be read on two
consecutive frames before it's accepted, to guard against rare misreads
on blurry frames.

The actual camera I/O runs on a dedicated background thread rather than
whatever thread calls start()/poll() (Tkinter's main thread, normally).
OpenCV's DirectShow backend relies on Windows COM, and COM's threading
rules mean that opening/reading the camera directly from a GUI toolkit's
own thread can silently produce a capture that "succeeds" (isOpened() is
True, read() returns True) but only ever delivers solid black frames —
a dedicated thread gets its own clean COM context and avoids that.

opencv-python and pyzbar are required for scanning to be offered at all
(scanner_available() returns False, and the UI falls back to manual entry,
if either is missing). zxing-cpp is optional on top of that — a nice
accuracy boost when present, silently skipped when not.

Install with:
    pip install opencv-python pyzbar zxing-cpp
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time

# Set BARCODE_SCAN_DEBUG=1 in the environment to print per-frame sharpness
# and raw (unfiltered) pyzbar reads to the console — useful for diagnosing
# why a real barcode isn't being picked up (too blurry vs. never detected
# vs. detected but filtered out by the EAN-13/978-979 check).
_DEBUG = os.environ.get("BARCODE_SCAN_DEBUG") == "1"

# When debugging, save numbered frames into this directory throughout the
# session (rather than overwriting a single file) so the whole session can
# be reviewed afterward — printed sharpness numbers don't show *what* the
# camera is actually seeing (framing, glare, focus).
_DEBUG_SNAPSHOT_DIR = os.environ.get("BARCODE_SCAN_DEBUG_SNAPSHOT_DIR")
if _DEBUG_SNAPSHOT_DIR:
    os.makedirs(_DEBUG_SNAPSHOT_DIR, exist_ok=True)


def scanner_available() -> bool:
    """Return True if both opencv-python and pyzbar are importable."""
    try:
        import cv2          # noqa: F401
        from pyzbar import pyzbar  # noqa: F401
        return True
    except ImportError:
        return False


def _zxingcpp():
    """Import zxingcpp if installed. It's optional — a second, generally
    more robust decode engine tried alongside pyzbar, not a hard dependency."""
    try:
        import zxingcpp
        return zxingcpp
    except ImportError:
        return None


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
    on_blur(is_blurry: bool, sharpness: float), if given, is called on
    every frame so the UI can show a live focus-quality readout — sharpness
    swings enormously with distance/positioning on real webcams, and a raw
    number the user can watch respond in real time turns out to matter more
    than any fixed distance advice, since every camera's sweet spot differs.

    All three callbacks are invoked from whatever thread calls poll() —
    normally the UI thread — never from the background capture thread, so
    they're safe to use directly with Tkinter widgets.
    """

    # Laplacian variance below this is treated as "too blurry to decode".
    # Tuned loosely — sharp, in-focus text/barcodes typically score in the
    # hundreds to thousands; a soft, defocused frame usually falls below 60.
    BLUR_THRESHOLD = 60.0

    # The live sharpness reading (and the barcode search) is computed on
    # this center fraction of the frame, matching the guide box the UI
    # draws over the preview — whole-frame sharpness is misleading, since
    # background clutter can score "sharp" while the barcode itself, held
    # off-center, is soft.
    ROI_FRACTION = 0.5

    # How many times to reopen the device if it comes up producing nothing
    # but solid black frames (see _open_and_warm_up).
    _OPEN_ATTEMPTS = 3

    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._cap = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._open_result: queue.Queue = queue.Queue(maxsize=1)

    def _open_and_warm_up(self, cv2) -> bool:
        """Open the capture device and burn through frames until real
        (non-black) content shows up, or give up after ~2s. Returns True if
        real content was seen."""
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

        # Right after opening (or after changing resolution), some
        # DirectShow drivers hand back "successful" reads that are just
        # solid black for a stretch while the capture graph finishes
        # negotiating the actual video stream — and on some UVC devices
        # this negotiation just fails outright for the lifetime of that
        # particular open() call, with no recovery short of reopening the
        # device (see the retry loop in _run). Burn through frames here
        # until we see real content, or give up after 2s.
        deadline = time.time() + 2.0
        warm_frame = None
        got_real_frame = False
        while time.time() < deadline:
            ret, warm_frame = self._cap.read()
            if ret and warm_frame is not None and warm_frame.std() > 3.0:
                got_real_frame = True
                break
        if _DEBUG:
            std = warm_frame.std() if warm_frame is not None else None
            print(f"[scan] warm-up done, last frame std={std}")
        return got_real_frame

    def _run(self, cv2) -> None:
        """Background-thread entry point: owns the capture device for its
        entire lifetime, from open through the read loop to release."""
        opened = False
        for attempt in range(self._OPEN_ATTEMPTS):
            if self._open_and_warm_up(cv2):
                opened = True
                break
            if _DEBUG:
                print(f"[scan] attempt {attempt + 1} produced no real frame, reopening")
            if self._cap is not None:
                self._cap.release()
                self._cap = None

        self._open_result.put(opened)
        if not opened:
            return

        debug_frame_count = 0
        last_candidate = None
        last_candidate_hits = 0

        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                continue

            if _DEBUG_SNAPSHOT_DIR:
                debug_frame_count += 1
                if debug_frame_count % 5 == 0:
                    path = os.path.join(_DEBUG_SNAPSHOT_DIR, f"frame_{debug_frame_count:04d}.png")
                    cv2.imwrite(path, frame)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            h, w = gray.shape[:2]
            margin = (1.0 - self.ROI_FRACTION) / 2.0
            y0, y1 = int(h * margin), int(h * (1.0 - margin))
            x0, x1 = int(w * margin), int(w * (1.0 - margin))
            roi = gray[y0:y1, x0:x1]

            sharpness = cv2.Laplacian(roi, cv2.CV_64F).var()
            is_blurry = sharpness < self.BLUR_THRESHOLD
            if _DEBUG:
                print(f"[scan] sharpness={sharpness:.1f} blurry={is_blurry}")

            # Skip the (relatively expensive) barcode search entirely on
            # frames too soft to decode anyway — neither decoder would find
            # anything, so this only saves CPU. Search the guide-box ROI
            # first (where we're asking the user to hold the barcode) and
            # fall back to the full frame in case it's off-center.
            isbn = None
            if not is_blurry:
                isbn = self._decode(cv2, roi) or self._decode(cv2, gray)
            found_isbn = None
            if isbn:
                # Require the same reading twice in a row before accepting
                # it. A single-frame hit is occasionally a motion-blurred
                # misread that still happens to pass the barcode's
                # checksum; requiring a repeat all but eliminates false
                # triggers without adding noticeable delay.
                if isbn == last_candidate:
                    last_candidate_hits += 1
                else:
                    last_candidate = isbn
                    last_candidate_hits = 1
                if last_candidate_hits >= 2:
                    found_isbn = isbn
            else:
                last_candidate = None
                last_candidate_hits = 0

            item = {"frame": frame, "blurry": is_blurry, "sharpness": sharpness, "isbn": found_isbn}
            try:
                self._frame_queue.put_nowait(item)
            except queue.Full:
                # UI thread is behind — drop the oldest queued frame in
                # favor of this newer one rather than backing up.
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frame_queue.put_nowait(item)
                except queue.Full:
                    pass

            if found_isbn:
                break

        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def start(self, on_frame, on_found, on_blur=None) -> bool:
        """Start the capture loop. Returns False if the camera can't open."""
        try:
            import cv2
        except ImportError:
            return False

        self._on_frame = on_frame
        self._on_found = on_found
        self._on_blur = on_blur
        self._frame_queue = queue.Queue(maxsize=2)
        self._open_result = queue.Queue(maxsize=1)
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(cv2,), daemon=True)
        self._thread.start()

        try:
            # Matches the worst case of _OPEN_ATTEMPTS retries at ~2s each,
            # plus slack for the device to actually open.
            opened = self._open_result.get(timeout=10.0)
        except queue.Empty:
            opened = False

        if not opened:
            self._running = False
            self._thread.join(timeout=1.0)
            self._thread = None
            return False

        return True

    def poll(self) -> bool:
        """Deliver at most one captured frame's results via the on_frame /
        on_blur / on_found callbacks. Returns False when stopped.

        Call this repeatedly from a Tkinter `after()` loop — it never
        blocks, since the actual camera I/O happens on a background thread.
        """
        if not self._running:
            return False

        try:
            item = self._frame_queue.get_nowait()
        except queue.Empty:
            return self._running

        # on_blur first so the UI has the latest sharpness/blurry state
        # in hand by the time on_frame draws the guide-box overlay.
        if self._on_blur:
            self._on_blur(item["blurry"], item["sharpness"])
        if self._on_frame:
            self._on_frame(item["frame"])

        if item["isbn"]:
            self._running = False
            if self._on_found:
                self._on_found(item["isbn"])

        return self._running

    def _decode(self, cv2, gray) -> str | None:
        """Try to decode an EAN-13 barcode from a grayscale *frame*. Returns the ISBN or None."""
        zxingcpp = _zxingcpp()
        if zxingcpp is not None:
            try:
                results = zxingcpp.read_barcodes(gray, formats=zxingcpp.BarcodeFormat.EAN13)
            except Exception:
                results = []
            for result in results:
                data = (result.text or "").strip()
                if _DEBUG:
                    print(f"[scan] zxingcpp raw read: format={result.format} data={data!r}")
                if data.isdigit() and len(data) == 13 and data[:3] in ("978", "979"):
                    return data

        try:
            from pyzbar import pyzbar
        except ImportError:
            return None

        # Plain grayscale decodes most well-lit, in-focus barcodes. When that
        # fails, retry against a contrast-boosted version — book covers are
        # often glossy or unevenly lit, which flattens the bars enough that
        # pyzbar can't find an edge.
        candidates = [gray, cv2.equalizeHist(gray)]

        # Restrict to EAN-13: it's the only symbology ISBN barcodes use, and
        # scanning for every symbology pyzbar supports risks decoding an
        # unrelated barcode (price tag, shelf label, another product in
        # frame) and misreporting it as the book's ISBN.
        symbols = [pyzbar.ZBarSymbol.EAN13]

        for image in candidates:
            if _DEBUG:
                for barcode in pyzbar.decode(image):
                    print(f"[scan] raw read (unrestricted): type={barcode.type} "
                          f"data={barcode.data.decode('utf-8', errors='ignore')!r}")
            barcodes = pyzbar.decode(image, symbols=symbols)
            for barcode in barcodes:
                data = barcode.data.decode("utf-8", errors="ignore").strip()
                if data.isdigit() and len(data) == 13 and data[:3] in ("978", "979"):
                    return data
        return None

    def stop(self) -> None:
        """Stop the capture loop and release the camera.

        Blocks briefly (at most one frame-read's worth of time, typically
        well under a second) until the background thread has actually
        released the device, so it's safe to immediately open a new
        BarcodeScanner on the same camera index right after this returns.
        """
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._cap = None
