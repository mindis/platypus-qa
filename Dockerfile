FROM python:3-onbuild

ENV PORT 8000
EXPOSE $PORT

COPY * /usr/src/app/
RUN pip install gunicorn && cd /usr/src/app && python setup.py install

CMD cd /usr/src/app && gunicorn flask_server:app  -w 4
