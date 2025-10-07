# Firecrest Streamer

A simple command-line interface (CLI) tool to **stream files over WebSocket** connections.

---

## ✨ Features
- Send and receive files securely via WebSocket.
- Simple CLI interface for both client and server modes.
- Token-based authentication.

---

## 🧰 Installation

### (Optional) Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

### Install Firecrest Streamer
```bash
pip install firecrest-streamer
```

---

## 🚀 Usage

### Run as a Client

To send or receive files, you need a **secret token** issued by the Firecrest Streamer server when a new transfer is initiated.

#### Receive a file:
```bash
streamer receive --token [secret-token] --path [destination-path]
```

#### Send a file:
```bash
streamer send --token [secret-token] --path [file-to-send]
```

> **Note:** The `--token` value must match the one provided by the server.  
> Both commands connect to the corresponding server endpoint.

---

### Run as a Server

You can also run your own Firecrest Streamer server to handle file transfers.

#### Start a server to send files:
```bash
streamer server --secret [your-secret-string] send --path [file-to-send]
```

#### Start a server to receive files:
```bash
streamer server --secret [your-secret-string] receive --path [destination-path]
```

> **Tip:** Use a unique `--secret` string to protect your server session.

---

## 🧑‍💻 Development

### Run from source

```bash
cd src
python -m streamer server --secret [your-secret-string] send --path [file-to-send]
python -m streamer receive --token [secret-token] --path [destination-path]
```

---

## 📦 Distribution

To build and publish a new version to PyPI:

```bash
python3 -m build --wheel
twine upload dist/*
```

> **Note:** Your PyPI API token should be stored in the local `.pypirc` file.

---

## 📝 License

This project is licensed under the BSD-3-Clause license. See the [LICENSE](https://github.com/eth-cscs/firecrest-v2/blob/master/LICENSE) file for details.


