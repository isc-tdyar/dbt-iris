# IRIS Community with the packages Python models need inside IRIS's Embedded Python.
# containers.intersystems.com has no `latest` tag, so a tag is required (issue #7).
ARG IMAGE=containers.intersystems.com/intersystems/iris-community:latest-cd
FROM ${IMAGE}

ENV PIP_TARGET=${ISC_PACKAGE_INSTALLDIR}/mgr/python

RUN python3 -m venv /tmp/pipv && \
  /tmp/pipv/bin/pip install --target ${ISC_PACKAGE_INSTALLDIR}/mgr/python pandas sqlalchemy sqlalchemy-iris && \
  rm -rf /tmp/pipv
