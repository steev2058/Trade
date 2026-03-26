import argparse
import asyncio
from app.core.settings import settings
from app.core.runner import TradingRunner


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["paper", "live"], default=settings.mode)
    p.add_argument("--confirm-live", default="")
    return p.parse_args()


async def _run():
    args = parse_args()
    if args.mode == "live" and args.confirm_live != "YES_I_ACCEPT_LIVE_TRADING":
        raise SystemExit("Live mode requires --confirm-live YES_I_ACCEPT_LIVE_TRADING")

    runner = TradingRunner(mode=args.mode)
    await runner.start()


if __name__ == "__main__":
    asyncio.run(_run())
