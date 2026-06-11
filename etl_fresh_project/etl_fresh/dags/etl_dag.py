"""
dags/etl_dag.py
Apache Airflow DAG — daily ETL schedule.
Week 4 - Day 1-3
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

default_args = {
    "owner":            "data-engineering",
    "depends_on_past":  False,
    "start_date":       days_ago(1),
    "email_on_failure": True,
    "email_on_retry":   False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}


def run_stripe_customers(**ctx):
    from orchestration.pipeline import ETLPipeline
    return ETLPipeline().run_stripe_customers(hours=25)


def run_stripe_payments(**ctx):
    from orchestration.pipeline import ETLPipeline
    return ETLPipeline().run_stripe_payments(hours=25)


def run_salesforce(**ctx):
    from orchestration.pipeline import ETLPipeline
    return ETLPipeline().run_salesforce_accounts(hours=25)


def run_zendesk(**ctx):
    from orchestration.pipeline import ETLPipeline
    return ETLPipeline().run_zendesk_tickets(hours=25)


def summary(**ctx):
    ti = ctx["ti"]
    print("Pipeline Summary:")
    for key in ["stripe_customers", "stripe_payments",
                "salesforce_accounts", "zendesk_tickets"]:
        val = ti.xcom_pull(key=key) or "N/A"
        print(f"  {key}: {val}")


with DAG(
    dag_id="enterprise_etl_pipeline",
    description="Daily ETL: Salesforce + Stripe + Zendesk → Data Warehouse",
    default_args=default_args,
    schedule_interval="0 2 * * *",   # Roz raat 2 baje
    catchup=False,
    tags=["etl", "production"],
    max_active_runs=1,
) as dag:

    t1 = PythonOperator(task_id="stripe_customers",    python_callable=run_stripe_customers)
    t2 = PythonOperator(task_id="stripe_payments",     python_callable=run_stripe_payments)
    t3 = PythonOperator(task_id="salesforce_accounts", python_callable=run_salesforce)
    t4 = PythonOperator(task_id="zendesk_tickets",     python_callable=run_zendesk)
    t5 = PythonOperator(task_id="summary",             python_callable=summary,
                        trigger_rule="all_done")

    [t1, t2, t3, t4] >> t5
