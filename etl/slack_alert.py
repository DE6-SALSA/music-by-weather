import requests
import json

from airflow.models import Variable

def slack_alert(context):
    dag_id = context.get('dag').dag_id
    task_id = context.get('task_instance').task_id
    execution_date = context.get('execution_date')
    log_url = context.get('task_instance').log_url
    webhook_url = Variable.get("SLACK_KEY")
    # webhook_url = "https://hooks.slack.com/services/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"

    message = {
        "text": (
            f":red_circle: *Airflow Task Failure Alert!*\n"
            f"*DAG*: `{dag_id}`\n"
            f"*Task*: `{task_id}`\n"
            f"*Execution Time*: `{execution_date}`\n"
            f"<{log_url}|View Logs>"
        )
    }

    headers = {'Content-Type': 'application/json'}
    requests.post(webhook_url, data=json.dumps(message), headers=headers)
