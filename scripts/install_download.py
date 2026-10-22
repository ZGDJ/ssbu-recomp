"""Bounded, hash-checked installer downloads; publish only complete files."""
import hashlib
import http.client
import os
import time
import urllib.error
import urllib.request


class DownloadError(OSError):
    pass


class DownloadIntegrityError(DownloadError):
    pass


def download(url, destination, sha256, report=print, *, attempts=3,
             idle_timeout=15, deadline_seconds=1800):
    """Retry transient network failures within one deadline. Never replace on failure.

    Each socket operation has an idle timeout; read1 avoids waiting for a whole
    large buffer before checking the total deadline or reporting received bytes.
    """
    if not sha256:
        raise ValueError('A pinned SHA-256 is required')
    part = os.fspath(destination) + '.download-part'
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    deadline = time.monotonic() + deadline_seconds
    last_error = None
    try:
        for attempt in range(1, attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            report('Download attempt %d/%d (network idle limit %ds)' % (attempt, attempts, idle_timeout))
            digest, received = hashlib.sha256(), 0
            last_report = time.monotonic()
            try:
                with urllib.request.urlopen(url, timeout=min(idle_timeout, remaining)) as response:
                    total = response.headers.get('Content-Length')
                    total = int(total) if total and total.isdigit() else None
                    with open(part, 'wb') as output:
                        read = getattr(response, 'read1', response.read)
                        while True:
                            if time.monotonic() >= deadline:
                                raise DownloadError('Download exceeded the %ds total time limit' % deadline_seconds)
                            block = read(64 * 1024)
                            if not block:
                                break
                            output.write(block)
                            digest.update(block)
                            received += len(block)
                            if time.monotonic() - last_report >= 5:
                                report('Downloaded %s bytes%s' % (format(received, ','),
                                       ' of %s' % format(total, ',') if total is not None else ''))
                                last_report = time.monotonic()
                if total is not None and received != total:
                    raise http.client.IncompleteRead(b'', total - received)
                if digest.hexdigest() != sha256:
                    raise DownloadIntegrityError('Download SHA-256 mismatch: refused (got %s)' % digest.hexdigest())
                if time.monotonic() >= deadline:
                    raise DownloadError('Download exceeded the %ds total time limit' % deadline_seconds)
                os.replace(part, destination)
                report('Download verified: %s bytes' % format(received, ','))
                return destination
            except DownloadError:
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as error:
                last_error = error
                report('Download interrupted (%s); %s' % (error,
                       'retrying' if attempt < attempts else 'retry limit reached'))
        raise DownloadError('Download failed after bounded retries/time limit: %s. Check your connection and press Retry.' % last_error)
    finally:
        try:
            os.remove(part)
        except FileNotFoundError:
            pass
