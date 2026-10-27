"""The PDF parser service: the same code as the sandbox, but this process serves ONLY
POST /parse-pdf and GET /health. There is no /run here, and no model-written code ever reaches it.
It runs in its own container on parse_net (shared with the api only), so the sandbox that runs
model code is on a different network from the api.
Start: `python -m indesk_sandbox.parser_server`."""

from indesk_sandbox import server


def main() -> None:
    server.serve(server.ParseHandler, "parser")


if __name__ == "__main__":
    main()
