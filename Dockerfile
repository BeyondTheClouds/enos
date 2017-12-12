FROM python:2.7

ADD . /tmp/enos

RUN pip install --no-cache-dir /tmp/enos && \
    pip install --no-cache-dir git+https://github.com/openstack/python-blazarclient && \
    rm -r /tmp/enos

ENTRYPOINT ["enos"]
