# **ASCI-Fight** allows you to fight with your teammates in style.

A Social Coding Interaction - Fight: allows for a couple of teams to fight against each other in a game of social coding and interaction. Outsmart your colleagues by building the best script bots and compete in various types of combat.

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

### Client Docker

1. Build the image

```
docker build -f ascifight/client_lib/Dockerfile -t ascifight_client .
```

2. Run the container

```
docker run --network="host" ascifight_client
```
