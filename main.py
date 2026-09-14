from config.settings import load_settings


def main() -> None:
    settings = load_settings()
    print(f"Garud AI Terminal — mode: {settings.trading_mode.value}")
    print(f"Kill switch enabled: {settings.kill_switch_enabled}")
    print("No pipeline stages wired up yet — this is the project skeleton.")


if __name__ == "__main__":
    main()
