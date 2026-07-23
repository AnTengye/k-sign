FROM ghcr.io/whyour/qinglong:2.20.2-debian

USER root

# Runtime shared libraries required by OpenCV (full build) and headless image ops.
# QingLong dependency management may install the full opencv-python into its
# dep_cache, which links against X11/GL libs not present in the base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libxcb1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libx11-6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/k-sign-requirements.txt

RUN python3 -m pip install \
        --no-cache-dir \
        --disable-pip-version-check \
        -r /tmp/k-sign-requirements.txt \
    && rm -f /tmp/k-sign-requirements.txt
