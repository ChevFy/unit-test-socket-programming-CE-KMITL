# UDP Reliable File Transfer - Docker Testing Environment

Complete Docker testing environment with network simulation and **real-time code updates** (no rebuild needed!).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Usage](#usage)
     - [Running Tests](#running-tests)
     - [Manual Testing](#manual-testing)
     - [Custom Files](#custom-files)
- [Configuration](#configuration)
     - [Editing config.json](#editing-configjson)
     - [Test Scenarios](#test-scenarios)
- [Development](#development)
     - [Real-Time Updates](#real-time-updates)
     - [When to Rebuild](#when-to-rebuild)
- [Docker Reference](#docker-reference)
     - [Container Management](#container-management)
     - [Network Debugging](#network-debugging)
     - [File Verification](#file-verification)
     - [Cleanup](#cleanup)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- **Docker** & **Docker Compose**
- **Python 3.7+**

## Quick Start

```bash
# 1. Build and start containers
docker compose up -d

# 2. Run a single test
python scripts/run_test.py 1

# Or run all tests
python scripts/run_test.py all

# 3. Edit your code in src/
# Changes are live - no rebuild needed!

# 4. Run tests again
python scripts/run_test.py 1
```

## Usage

### Running Tests

```bash
# Single test (1-8)
python scripts/run_test.py 3

# All tests
python scripts/run_test.py all
```

### Manual Testing

```bash
# Server (already running in container)
docker logs -f urft_server

# Client
docker exec -it urft_client python /app/src/urft_client.py /app/test/testfile.bin 172.25.0.10 12345
```

### Custom Files

Test with your own files instead of generated random data:

```bash
# Test with PDF, image, video, etc.
python scripts/run_test.py 3 --file myfile.pdf
python scripts/run_test.py 1 --file document.docx
python scripts/run_test.py 5 --file video.mp4
```

## Configuration

### Editing config.json

Edit `config.json` to customize tests (changes apply immediately):

```json
{
	"tests": [
		{
			"id": 1,
			"file_size_mb": 1, // Change file size
			"timeout": 30, // Change timeout
			"network_conditions": {
				"client": {
					"delay": "5ms", // Add delay
					"loss": "2%", // Add packet loss
					"duplicate": null, // Add duplication
					"reorder": null // Add reordering
				}
			}
		}
	]
}
```

### Test Scenarios

Pre-configured test scenarios (edit in `config.json`):

| Test | File Size | RTT   | Client Conditions | Server Conditions | Timeout |
| ---- | --------- | ----- | ----------------- | ----------------- | ------- |
| 1    | 1 MB      | 10ms  | -                 | -                 | 30s     |
| 2    | 1 MB      | 10ms  | Dup: 2%           | -                 | 30s     |
| 3    | 1 MB      | 10ms  | Loss: 2%          | -                 | 30s     |
| 4    | 1 MB      | 10ms  | -                 | Dup: 5%           | 30s     |
| 5    | 1 MB      | 10ms  | -                 | Loss: 5%          | 30s     |
| 6    | 1 MB      | 250ms | -                 | -                 | 60s     |
| 7    | 1 MB      | 250ms | Reorder: 2%       | -                 | 90s     |
| 8    | 5 MB      | 100ms | Loss: 5%          | Loss: 2%          | 30s     |

## Development

### Real-Time Updates

**No rebuild needed!** Edit files on your host and changes apply instantly:

1. **Edit source code:**
     - `src/urft_client.py`
     - `src/urft_server.py`

2. **Edit configuration:**
     - `config.json`

3. **Test immediately:**
     ```bash
     python scripts/run_test.py 1  # Changes already applied!
     ```

**Volume Mounts:**

- `./src` → `/app/src` (live code updates)
- `./config.json` → `/app/config.json` (live config updates)
- `./test` & `./recived` → File storage

### When to Rebuild

Only rebuild if you modify:

- `Dockerfile`
- `docker-compose.yml`
- System dependencies

**Rebuild command:**

```bash
docker-compose up -d --build
```

## Docker Reference

### Container Management

```bash
# Start containers
docker-compose up -d

# Stop containers
docker-compose down

# View logs
docker logs -f urft_server
docker logs -f urft_client

# Shell access
docker exec -it urft_server bash
docker exec -it urft_client bash
```

### Network Debugging

```bash
# Check network conditions
docker exec urft_client tc qdisc show dev eth0

# Clear network rules
docker exec urft_client tc qdisc del dev eth0 root 2>/dev/null
```

### File Verification

```bash
# Check MD5 hashes
docker exec urft_test md5sum /app/test/testfile.bin
docker exec urft_server md5sum /app/recived/testfile.bin
```

### Cleanup

```bash
# Cross-platform cleanup
python scripts/cleanup.py

# Manual cleanup
docker-compose down -v
rm -rf test/* recived/*
```

## Project Structure

```
├── src/
│   ├── urft_client.py         # UDP client (edit for live updates!)
│   └── urft_server.py         # UDP server (edit for live updates!)
├── scripts/
│   ├── run_test.py            # Test runner
│   ├── cleanup.py             # Cleanup script
│   └── network_setup.sh       # Network conditions (in container)
├── test/                      # Test files
├── recived/                   # Received files
├── Dockerfile                 # Container image
├── docker-compose.yml         # Container orchestration
├── config.json                # Test configuration (edit for live updates!)
└── README.md
```

**Container Network:**

- **server**: `172.25.0.10:12345`
- **client**: `172.25.0.20`
- **test**: `172.25.0.30`
- Network: `172.25.0.0/16` bridge with NET_ADMIN capabilities

## Troubleshooting

**Containers won't start:**

```bash
# Check logs
docker-compose logs

# Rebuild containers
docker-compose up -d --build
```

**Network conditions not working:**

```bash
# Verify tc is installed
docker exec urft_client tc -V

# Check current rules
docker exec urft_client tc qdisc show dev eth0
```

**File transfer fails:**

```bash
# Check server is running
docker exec urft_server ps aux | grep python

# View server logs
docker logs -f urft_server

# Restart server manually
docker exec -it urft_server python /app/src/urft_server.py 0.0.0.0 12345
```

**Code changes not reflected:**

```bash
# Verify volume mount
docker exec urft_server ls -la /app/src/

# Check file contents
docker exec urft_server cat /app/src/urft_server.py | head -20
```
