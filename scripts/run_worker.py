import argparse
import importlib.util
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

spec = importlib.util.spec_from_file_location("lexibridge_app", BACKEND / "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


def main():
    parser = argparse.ArgumentParser(description="Run LexiBridge AI local background worker.")
    parser.add_argument("--worker-id", default=app_module.JOB_WORKER_ID)
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    with app_module.app.app_context():
        app_module.db.create_all()
        app_module.ensure_schema_columns()
        while True:
            job = app_module.run_worker_once(worker_id=args.worker_id)
            if job is None:
                if args.once:
                    print("no queued jobs")
                    return
                time.sleep(args.interval)
                continue
            print(f"processed job_id={job.id} type={job.job_type} status={job.status}")
            if args.once:
                return


if __name__ == "__main__":
    main()
