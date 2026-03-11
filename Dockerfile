FROM python:3.11

RUN apt update && apt install -y ffmpeg

WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

CMD ["python", "Bot_zabawa_g.py"]
