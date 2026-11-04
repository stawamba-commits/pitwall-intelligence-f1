"""Shared by the two PitWall DAGs: Snowflake settings, mounts, failure alert, Docker task factory.
(No DAG in this file, so importing it twice never registers a DAG twice.)"""
import json
import os
import urllib.request

from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

SNOWFLAKE_ENV = {
    "SNOWFLAKE_ACCOUNT": os.environ["SNOWFLAKE_ACCOUNT"],
    "SNOWFLAKE_USER": os.environ["SNOWFLAKE_USER"],
    "SNOWFLAKE_PRIVATE_KEY_FILE": "/secrets/rsa_key.p8",
    "PITWALL_RUN_ID": "{{ run_id }}",                      # written in every bronze row (_RUN_ID)
}
# The key is mounted read-only at run time: it is never inside an image.
KEY_MOUNT = [Mount(source=os.environ["PITWALL_KEYS_DIR"], target="/secrets", type="bind", read_only=True)]
CACHE_MOUNT = [Mount(source=os.environ["PITWALL_FASTF1_CACHE"], target="/cache", type="bind")]


def alert_on_failure(context):
    """Course: airflow_slack_alert_callback.py. Fires after the LAST retry."""
    ti = context["task_instance"]
    text = (f":red_circle: PitWall *{ti.dag_id}.{ti.task_id}* failed for {context['ds']} "
            f"(attempt {ti.try_number}). Logs: {ti.log_url}")
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if not url:
        print("ALERT (no ALERT_WEBHOOK_URL set):", text)
        return
    req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def job(task_id, command, image="pitwall-jobs:1.0.0", mounts=None, **env):
    """One task = one container run of our image."""
    return DockerOperator(
        task_id=task_id, image=image, command=command,
        environment={**SNOWFLAKE_ENV, **env},
        mounts=KEY_MOUNT + (mounts or []),
        mount_tmp_dir=False, auto_remove="success")
