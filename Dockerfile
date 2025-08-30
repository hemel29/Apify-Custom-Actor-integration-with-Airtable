FROM apify/actor-python:3.11

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Google Chrome + runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg wget unzip ca-certificates \
    fonts-liberation xdg-utils libnss3 libasound2 libu2f-udev libgbm1 \
    libgtk-3-0 libglib2.0-0 libgdk-pixbuf2.0-0 libdrm2 libxdamage1 libx11-xcb1 libpangocairo-1.0-0 \
 && wget -qO- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-linux.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
 && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
 && rm -rf /var/lib/apt/lists/*

# (We rely on Selenium Manager to fetch the correct chromedriver)
ENV CHROME_BIN=/usr/bin/google-chrome

COPY . .
CMD ["python", "main.py"]

# FROM apify/actor-python:3.11
# WORKDIR /app
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
# COPY . .
# CMD ["python", "main.py"]

# FROM apify/actor-python:3.13


# WORKDIR /app
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# COPY requirements.txt ./

# # Install the packages specified in requirements.txt,
# # Print the installed Python version, pip version
# # and all installed packages with their versions for debugging
# RUN echo "Python version:" \
#  && python --version \
#  && echo "Pip version:" \
#  && pip --version \
#  && echo "Installing dependencies:" \
#  && pip install -r requirements.txt \
#  && echo "All installed Python packages:" \
#  && pip freeze

# # Next, copy the remaining files and directories with the source code.
# # Since we do this after installing the dependencies, quick build will be really fast
# # for most source file changes.
# COPY . ./

# # Use compileall to ensure the runnability of the Actor Python code.
# RUN python3 -m compileall -q .


# # Specify how to launch the source code of your Actor.
# # By default, the "python3 -m src" command is run
# CMD ["python3", "-m", "main"]