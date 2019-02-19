FROM python:3-alpine

ADD target/job /app/job
ADD target/python-library /app/python-library

RUN pip install /app/python-library
RUN pip install /app/job
RUN chmod -R +x /app/job/src/scripts/

ENTRYPOINT ["/app/job/src/scripts/job_executor.py"]
