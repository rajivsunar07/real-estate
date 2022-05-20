FROM python:3-slim
RUN apt-get update \
    && apt-get -y install libpq-dev gcc
ADD . /flask-app
WORKDIR /flask-app
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
EXPOSE 5000
CMD gunicorn app:app
