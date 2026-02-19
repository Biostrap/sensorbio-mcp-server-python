import os

from sensorbio_mcp_server.sensr_client import SensrClient


def main() -> None:
    if not os.getenv("SENSR_API_KEY"):
        raise SystemExit("Set SENSR_API_KEY before running smoke test")

    client = SensrClient.from_env()
    data = client.request("GET", "/v1/organizations/users/ids")
    print("OK: /v1/organizations/users/ids")
    print(data)


if __name__ == "__main__":
    main()
