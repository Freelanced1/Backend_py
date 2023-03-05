FROM python:3.10.0

# copy files to the /app folder in the container
COPY ./main.py /app/main.py
COPY ./requirements.txt /app/requirements.txt

# set the working directory in the container to be /app
WORKDIR /app

# install the packages from the Pipfile in the container
RUN pip install --no-cache-dir --upgrade -r requirements.txt


# expose the port that uvicorn will run the app on
ENV PORT=8000
EXPOSE 8000
RUN export PYTHONPATH=$PWD

# execute the command python main.py (in the WORKDIR) to start the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]