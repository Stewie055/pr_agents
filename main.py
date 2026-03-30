from pr_agents.bootstrap import build_api_app

import uvicorn


def main() -> None:
    uvicorn.run(build_api_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
