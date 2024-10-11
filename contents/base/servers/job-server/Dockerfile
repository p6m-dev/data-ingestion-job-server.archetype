# Use an official Python runtime as a parent image
#FROM python:3.8-slim
FROM ubuntu:latest


# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

#COPY /requirements.txt /tmp/
RUN apt update && apt upgrade -y
RUN apt install -y python3-pip
RUN pip3 install fastapi[all]
RUN pip3 install sqlalchemy
RUN pip3 install psycopg2-binary
RUN pip3 install requests
RUN pip3 install uvicorn


# Make port 8000 available to the world outside this container
EXPOSE $PORT

# Define environment variable
ENV HOST 0.0.0.0
ENV PORT 80

CMD python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 80

# Run app.py when the container launches
#CMD ["uvicorn", "main:app", "--host", ${HOST}, "--port", ${PORT}]
#CMD ["/bin/sleep", "3650d"]

