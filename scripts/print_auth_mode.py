"""Print which Sensr auth mode is active based on environment variables.

Does not print any secrets.
"""

from sensorbio_mcp_server.sensr_client import SensrClient, SensrError


def main() -> None:
    try:
        client = SensrClient.from_env()
    except SensrError as e:
        print(f"auth_mode=error ({e})")
        raise SystemExit(2)

    print(f"auth_mode={client.auth_mode()}")


if __name__ == "__main__":
    main()
