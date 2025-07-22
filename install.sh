#!/bin/sh

# Check that we're root so we can symlink to `/usr/local/bin/dc`
if [ "$(id -u)" -ne 0 ]
  then echo "Please run as root for symlink creation."
  exit
fi

cd "$(dirname "$0")"

# Create a venv for deps
if [ ! -d ".venv" ]; then
  echo "Creating python virtual environment"
  python3 -m venv .venv
  .venv/bin/pip3 install -r requirements.txt
else
  echo ".venv already created; skipping."
fi

# If we had an existing symlink, remove it.
if [ -L /usr/local/bin/dc ]; then
  rm /usr/local/bin/dc
fi

# Finally, link to our current dc.sh file, that wraps our dc.py
ln -s $(pwd)/dc.sh /usr/local/bin/dc
