FROM python:2-alpine

ADD target/job/src/nuvla /usr/local/lib/python2.7/site-packages/nuvla
ADD target/job/src/scripts /opt/nuvla/job/sbin 
      
# need to add nuvla python library
# RUN pip install -Iv nuvla-api

RUN pip install -Iv kazoo
RUN pip install -Iv elasticsearch
RUN pip install -Iv boto3

ENV ZK_HOST=zk
ENV ZK_PORT=2181
ENV API_HOST=api
ENV API_PORT=443

ENTRYPOINT ["/opt/nuvla/job/sbin/job_executor.py"]
