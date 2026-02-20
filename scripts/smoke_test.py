from sensorbio_mcp_server.sensr_client import SensrClient


def main() -> None:
    client = SensrClient.from_env()
    data = client.request("GET", "/v1/organizations/users/ids")
    print(f"OK: /v1/organizations/users/ids (auth_mode={client.auth_mode()})")
    print(data)


if __name__ == "__main__":
    main()
