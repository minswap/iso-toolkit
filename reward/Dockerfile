FROM python:3.10

RUN apt-get update -y \
    && apt-get install -y libpq-dev \
    && pip install psycopg2-binary

WORKDIR /smallest

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy Pipenv files to the working directory
COPY reward/Pipfile reward/Pipfile.lock /smallest/

# Install pipenv and project dependencies
RUN pip install pipenv && pipenv install

# Copy the rest of the application code to the working directory
COPY reward /smallest
