# Test package
import atexit
import os
import shutil
import tempfile

if not os.getenv("SIGN_SUMMARY_DIR"):
    _TEST_SUMMARY_DIR = tempfile.mkdtemp(prefix="ksign-test-summary-")
    os.environ["SIGN_SUMMARY_DIR"] = _TEST_SUMMARY_DIR
    atexit.register(lambda: shutil.rmtree(_TEST_SUMMARY_DIR, ignore_errors=True))
