"""Release request memory without finalizing inherited native sessions."""

import os


def worker_exit(_server, worker):
    # Native ONNX destructors can wait on parent threads after a preloaded fork.
    if worker.pid == os.getpid():
        os._exit(0)
