# Set up Terml.io as a local Git repository
These instructions have been fined-tuned for OS X. The same commands should probably work for Linux. On Windows, please consider using Cygwin.

## OS X
Tested with OS X Yosemite. You will need sudo (administrator) access.

1. Install pip if you haven't already done so.
  ```bash
  sudo easy_install pip
  ```

2. Clone Terml.io to local repo.
  ```bash
  git clone https://github.com/justinpotts/terml.io.git
  ```

3. Install Flask and other dependencies.
  ```bash
  sudo -H pip install -r requirements.txt
  ```
4. Edit termlio.py and comment out other databases except for the one designated for local instances. It should be SQLite.

5. Run some Python to set up the database.
  ```python
  python
  from termlio import db
  db.create_all()
  ```

6. To run Terml.io, put this in the command line:
  ```bash
  python termlio.py
  ```
