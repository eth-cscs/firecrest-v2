import requests


def check_liveness():
    try:
        # Fetch the JSON response
        response = requests.get("http://localhost:5000/status/liveness/", timeout=5)
        response.raise_for_status()
        data = response.json()

        # Check if within 15 minutes
        if data["lastUpdate"] >= 0 and data["lastUpdate"] <= 900:
            return 0
        else:
            print("Updates are stale...")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(check_liveness())
