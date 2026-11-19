"""Launch the backtest API development server"""

import uvicorn

def main() -> None:
    uvicorn.run(
        "river_backtest.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

if __name__ == "__main__":
    main()