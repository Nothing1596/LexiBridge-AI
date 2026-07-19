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
        prefer_formal = True
        while True:
            formal_result = None
            legacy_job = None
            if prefer_formal:
                formal_result = app_module.run_formal_worker_once(worker_id=args.worker_id)
                if formal_result.outcome == "no_job_available":
                    legacy_job = app_module.run_worker_once(worker_id=args.worker_id)
            else:
                legacy_job = app_module.run_worker_once(worker_id=args.worker_id)
                if legacy_job is None:
                    formal_result = app_module.run_formal_worker_once(worker_id=args.worker_id)
            prefer_formal = not prefer_formal

            if legacy_job is None and (formal_result is None or formal_result.outcome == "no_job_available"):
                if args.once:
                    print("no queued jobs")
                    return
                time.sleep(args.interval)
                continue
            if legacy_job is not None:
                print(f"processed job_id={legacy_job.id} type={legacy_job.job_type} status={legacy_job.status}")
            else:
                print(
                    "processed formal "
                    f"job_uid={formal_result.job_uid} "
                    f"run_uid={formal_result.workflow_run_uid} "
                    f"status={formal_result.job_status} "
                    f"outcome={formal_result.outcome}"
                )
            if args.once:
                return


if __name__ == "__main__":
    main()
