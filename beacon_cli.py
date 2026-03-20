// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import argparse
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from beacon_dashboard import create_beacon_app


def setup_logging(verbose=False):
    """Configure logging for beacon CLI"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_config(config_path=None):
    """Load configuration from file or environment"""
    config = {
        'DEBUG': os.getenv('BEACON_DEBUG', 'false').lower() == 'true',
        'HOST': os.getenv('BEACON_HOST', '127.0.0.1'),
        'PORT': int(os.getenv('BEACON_PORT', '5000')),
        'DATABASE_PATH': os.getenv('BEACON_DB_PATH', 'beacon.db'),
        'EXPORT_PATH': os.getenv('BEACON_EXPORT_PATH', 'exports/'),
        'SOUND_ALERTS': os.getenv('BEACON_SOUND_ALERTS', 'false').lower() == 'true',
        'REFRESH_INTERVAL': int(os.getenv('BEACON_REFRESH_INTERVAL', '5')),
    }

    if config_path and os.path.exists(config_path):
        # Load from config file if provided
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        config[key] = value
        except Exception as e:
            logging.warning(f"Failed to load config from {config_path}: {e}")

    return config


def validate_environment():
    """Check that required dependencies are available"""
    try:
        import flask
        import sqlite3
    except ImportError as e:
        print(f"Error: Missing required dependency: {e}")
        print("Please install required packages: pip install flask")
        return False

    return True


def launch_dashboard(args):
    """Launch the beacon dashboard"""
    if not validate_environment():
        return 1

    config = load_config(args.config)

    # Override config with command line arguments
    if args.host:
        config['HOST'] = args.host
    if args.port:
        config['PORT'] = args.port
    if args.debug:
        config['DEBUG'] = True
    if args.database:
        config['DATABASE_PATH'] = args.database
    if args.export_dir:
        config['EXPORT_PATH'] = args.export_dir
    if args.sound_alerts is not None:
        config['SOUND_ALERTS'] = args.sound_alerts
    if args.refresh_interval:
        config['REFRESH_INTERVAL'] = args.refresh_interval

    # Ensure export directory exists
    export_dir = Path(config['EXPORT_PATH'])
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        app = create_beacon_app(config)

        print(f"Starting Beacon Dashboard v1.1")
        print(f"Dashboard URL: http://{config['HOST']}:{config['PORT']}")
        print(f"Database: {config['DATABASE_PATH']}")
        print(f"Export directory: {config['EXPORT_PATH']}")
        if config['SOUND_ALERTS']:
            print("Sound alerts: ENABLED")
        print("Press Ctrl+C to stop")
        print("-" * 50)

        app.run(
            host=config['HOST'],
            port=config['PORT'],
            debug=config['DEBUG'],
            threaded=True
        )

    except KeyboardInterrupt:
        print("\nShutting down beacon dashboard...")
        return 0
    except Exception as e:
        logging.error(f"Failed to start beacon dashboard: {e}")
        if config['DEBUG']:
            import traceback
            traceback.print_exc()
        return 1

    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Beacon Dashboard v1.1 - Live transport traffic monitoring',
        prog='beacon'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Dashboard command
    dashboard_parser = subparsers.add_parser(
        'dashboard',
        help='Launch the beacon dashboard web interface'
    )

    dashboard_parser.add_argument(
        '--host',
        default=None,
        help='Host to bind to (default: 127.0.0.1)'
    )

    dashboard_parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Port to listen on (default: 5000)'
    )

    dashboard_parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    dashboard_parser.add_argument(
        '--config',
        help='Path to configuration file'
    )

    dashboard_parser.add_argument(
        '--database',
        help='Path to SQLite database file'
    )

    dashboard_parser.add_argument(
        '--export-dir',
        help='Directory for exported files'
    )

    dashboard_parser.add_argument(
        '--sound-alerts',
        type=lambda x: x.lower() == 'true',
        help='Enable/disable sound alerts (true/false)'
    )

    dashboard_parser.add_argument(
        '--refresh-interval',
        type=int,
        help='Dashboard refresh interval in seconds'
    )

    dashboard_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(getattr(args, 'verbose', False))

    if args.command == 'dashboard':
        return launch_dashboard(args)

    return 1


if __name__ == '__main__':
    sys.exit(main())
