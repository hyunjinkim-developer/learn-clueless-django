# Clue-Less

## Development Log
The development log is in progress. You can track updates [https://hyunjinkimdeveloper.notion.site/Clue-Less-1a421801a53980059dbcc9c29b1b382f?pvs=4]

## Setup
### Installation Manual
1. Install dependencies
% cd move-to-the-root-of-project-directory
% activate-virtual-environment
% pip install -r requirements.txt

## Test Instructions
1. Run the server
    1-1. Run Redis server
    % redis-server
    1-2. Run Django server
    % python manage.py runserver
        - When Django server doesn't start with ASGI:
            with terminal log “Starting ASGI/Channels development server…”
            run the script below so that the server listens both HTTP (pages) and WebSocket (live) connections.
            You can see why it is needed and how it works on https://www.notion.so/hyunjinkimdeveloper/Clue-Less-1a421801a53980059dbcc9c29b1b382f#1a821801a53980b39c8ced3d368ff56d
            % python run_daphne.py

## Messaging Protocols

