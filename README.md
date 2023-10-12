# **ASCI-Fight** allows you to fight with your teammates in style.

A Social Coding Interaction - Fight: allows for a couple of teams to fight against each other in a game of social coding and interaction. Outsmart your colleagues by building the best script bots and compete in various types of combat.

This repository consists of to parts:

- The server that is hosting the game engine and its interfaces and supplies the game rules.
- The client that gives commands to the actors of a team. Its the objective of a team to improve the existing logic code so that the team wins more games than others.

## Installing

### Server Docker

1. Build the image

```
docker build -t ascifight .
```

2. Run the container

```
docker run -p 0.0.0.0:8000:8000 ascifight .
```

3. Check your browser

http://127.0.0.1:8000/docs

Here you will find documentation about the server and its available endpoints to steer. your team to victory.
Configure the server using: server_config.toml

### Client Docker

1. Build the image

```
docker build -f ascifight/client_lib/Dockerfile -t ascifight_client .
```

2. Run the container

```
docker run --network="host" ascifight_client
```

## Client Lib

The client is located in the client_lib directory. Important files are:

- client.py: The executable that manages the basic interaction with the server
- logic.py: The file that contains the basic game logic. It uses
  - infra.py: Basic function that encapsulate interaction with the server
  - agents.py: Simple agents that encapsulate certain behavior and showcase the infrastructure
  - metrics.py: path-finding and distance calculations
  - basic_functions.py: basic functionality using path-finding and distance
  - state.py: a general game state class that supplies 4 classes:
    - Objects: returns all objects in the game
    - Rules: the current game rules
    - Conditions: higher level abstractions and statements about the game state
    - Actions: Actions that have been successfully performed by all teams during the game
- client_config.toml: A config file for the client

There is a testing client test_client.py that can be sued to test an team against itself. Note that it does not use the team names and passwords from the .toml file, but has hardcoded ones.
