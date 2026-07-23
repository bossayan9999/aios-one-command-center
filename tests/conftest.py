import os

# Existing regression tests focus on their own feature contracts.
# Dedicated Phase 1A tests disable this bypass and exercise the real boundary.
os.environ.setdefault("AIOS_SECURITY_TEST_BYPASS", "1")
