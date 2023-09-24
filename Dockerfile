FROM ubuntu:22.04

USER root
WORKDIR /home/user

# updating and setting up python
RUN apt update
RUN apt upgrade -y
RUN apt install -y python3 python3-pip
RUN pip3 install --upgrade pip
RUN pip3 install --upgrade setuptools

# installing all the dependencies
RUN pip3 install fastapi
RUN pip3 install pydantic
RUN pip3 install uvicorn
RUN pip3 install structlog
RUN pip3 install context-logging
RUN pip3 install toml
RUN pip3 install pillow
RUN pip3 install structlog
RUN pip3 install toml
RUN pip3 install pillow
RUN pip3 install httpx
RUN pip3 install vpython

# copying code
COPY ascifight/ ascifight/
COPY tests/ tests/

# the server is available in port 8000
EXPOSE 8000

# setting pythonpatj
ENV PYTHONPATH "${PYTHONPATH}:/home/user"

