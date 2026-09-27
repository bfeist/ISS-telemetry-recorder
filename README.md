# ISS Telemetry Recorder

This application records telemetry data from the International Space Station (ISS).

## Using the Docker Image

### Pull the image from GitHub Container Registry

```bash
# changed: update tag to 'main'
docker pull ghcr.io/bfeist/iss-telemetry-recorder:main
```

### Run with Docker

```bash
docker run -d \
  --name iss-telemetry \
  --restart unless-stopped \
  -v /path/on/host:/data \
  ghcr.io/bfeist/iss-telemetry-recorder:main
```

### Run with Docker Compose

Create a docker-compose.yml file:

```yaml
version: "3"

services:
  iss-telemetry:
    image: ghcr.io/bfeist/iss-telemetry-recorder:main
    container_name: iss-telemetry-recorder
    restart: unless-stopped
    volumes:
      - ${HOST_RAW_FOLDER:-./data}:/data
    environment:
      - RAW_FOLDER=/data
    tty: true
```

Then run:

```bash
# For Unraid, set HOST_RAW_FOLDER via the Docker GUI.
# Locally (e.g., in Git Bash), run:
HOST_RAW_FOLDER=./data docker-compose up -d
```

## Building Locally

If you prefer to build the Docker image locally:

```bash
# Clone the repository
git clone https://github.com/bfeist/ISS-telemetry-recorder.git
cd ISS-telemetry-recorder

# Build the Docker image
docker build -t iss-telemetry-recorder -f docker/dockerfile .

# Run the Docker container
docker run -d --name iss-telemetry --restart unless-stopped -v ./data:/data iss-telemetry-recorder
```

## Outage recovery

The recorder retries indefinitely when the server is unreachable or connected
but sends no telemetry for 60 seconds. Recovery attempts back off from 30 seconds
to at most 5 minutes, and the delay resets when updates resume. Subscriptions are
retained across reconnects. Stopping the container still stops the recorder.

The image healthcheck checks the recorder's main loop heartbeat, independently
of upstream data availability. A healthy container may be waiting for telemetry;
its logs show reconnect attempts and when telemetry resumes.

In Unraid, enable **Autostart** and set **Extra Parameters** (Advanced View) to
`--restart=unless-stopped`. Autostart alone does not restart a crashed container.
Saving the restart policy in the template preserves it across image updates.

Run the outage regression tests with `python -m unittest discover -s tests -v`.
