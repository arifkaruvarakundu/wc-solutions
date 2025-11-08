import os
import redis
import time
from dotenv import load_dotenv
load_dotenv()
from celery import Celery, shared_task, chain
from celery.schedules import crontab
# from tasks.fetch_products import fetch_and_save_products
from customers.operation_helper import function_get_dead_customers
from tasks.sending_to_dead_customers import send_whatsapp_dead_customer_message
from tasks.whatsapp_msg_after_one_month import send_whatsapp_message_after_one_month
from tasks.sending_to_low_churn_customers import helper_function_to_sending_message_to_low_churn_risk_customers, send_whatsapp_forecast_message
from database import SessionLocal
from models import Client
from tasks.fetch_orders import fetch_orders_task
from tasks.fetch_products import fetch_products_task
from datetime import datetime

# Get Redis URL from environment, or construct it with fallback defaults
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL not set in environment")

# Wait for Redis to be ready (Docker-friendly)
def wait_for_redis(max_retries=10, delay=2):
    for attempt in range(max_retries):
        try:
            r = redis.Redis.from_url(REDIS_URL)
            r.ping()
            print("✅ Redis ready")
            return
        except redis.exceptions.ConnectionError:
            print(f"⏳ Waiting for Redis... ({attempt+1}/{max_retries})")
            time.sleep(delay)
    raise RuntimeError("❌ Could not connect to Redis after retries")

wait_for_redis()

celery = Celery(
    "crm_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    # Tasks are defined below using @celery.task decorators
)

# optional: more robust broker retries for Kombu/Celery internals
celery.conf.broker_transport_options = {
    "max_retries": 5,
    "interval_start": 0,
    "interval_step": 1,
    "interval_max": 5,
}

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_scheduler='celery.beat.PersistentScheduler',
)

@shared_task(name="mark_sync_complete_task")
def mark_sync_complete_task(_, client_id):
    """
    Marks client sync as complete after the onboarding chain finishes.
    `_` is the previous result (ignored).
    """
    print(f"🏁 Finalizing sync for client_id={client_id}")
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client:
            client.sync_status = "COMPLETE"
            client.last_synced_at = datetime.utcnow()
            db.commit()
            print(f"✅ Sync complete for {client.email}")
    except Exception as e:
        print(f"❌ Error marking sync complete: {e}")
    finally:
        db.close()


@shared_task(name="onboard_new_client_task")
def onboard_new_client_task(client_id):
    """
    Runs immediately after a new client registers:
    1. Fetch products
    2. Then fetch orders
    """
    print(f"🚀 Starting onboarding for client_id={client_id}")
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client:
            client.sync_status = "IN_PROGRESS"
            db.commit()
            print(f"🔄 Sync started for {client.email}")
    finally:
        db.close()

    # Chain ensures fetch_orders runs *after* fetch_products completes
    workflow = chain(
        fetch_products_task.si(client_id=client_id),
        fetch_orders_task.si(client_id=client_id, full_fetch=True)
    )
    # add a callback to mark completion once the chain finishes
    workflow.apply_async(link=mark_sync_complete_task.s(client_id=client_id))
    print(f"✅ Onboarding workflow queued for client_id={client_id}")

@shared_task(name="fetch_all_clients_orders_task")
def fetch_all_clients_orders_task():
    """
    Periodic task that fetches orders for all currently logged-in clients.
    Runs every minute via Celery Beat.
    """
    db = SessionLocal()
    try:
        # Fetch only logged-in clients with valid credentials
        clients = db.query(Client).filter(
            Client.is_logged_in.is_(True),
            Client.store_url != None,
            Client.consumer_key != None,
            Client.consumer_secret != None
        ).all()

        if not clients:
            print("⚠️ No active clients. Skipping periodic sync.")
            return

        print(f"🔄 Periodic sync: Found {len(clients)} active clients")

        for client in clients:
            try:
                # Trigger full fetch only if never synced before
                is_first_sync = client.last_synced_at is None
                
                # Use apply_async to avoid blocking
                fetch_orders_task.apply_async(
                    kwargs={
                        'client_id': client.id,
                        'full_fetch': is_first_sync
                    },
                    # Add to queue with priority (lower number = higher priority)
                    priority=0 if is_first_sync else 5
                )
                
                print(f"✅ Enqueued {'full' if is_first_sync else 'incremental'} sync for {client.email}")
            except Exception as e:
                print(f"⚠️ Could not enqueue fetch_orders_task for {client.email}: {e}")
    finally:
        db.close()

@shared_task(name="fetch_all_clients_products_task")
def fetch_all_clients_products_task():
    """
    Periodic task that fetches products for all currently logged-in clients.
    Runs every 2 hours via Celery Beat.
    """
    db = SessionLocal()
    try:
        # Fetch only logged-in clients with valid WooCommerce credentials
        clients = db.query(Client).filter(
            Client.is_logged_in.is_(True),
            Client.store_url != None,
            Client.consumer_key != None,
            Client.consumer_secret != None
        ).all()

        if not clients:
            print("⚠️ No active clients. Skipping periodic product sync.")
            return

        print(f"🔄 Periodic product sync: Found {len(clients)} active clients")

        for client in clients:
            try:
                # Use apply_async to run per-client product fetching asynchronously
                fetch_products_task.apply_async(
                    kwargs={'client_id': client.id},
                    priority=5  # lower priority than full order syncs
                )
                print(f"✅ Enqueued product sync for {client.email}")
            except Exception as e:
                print(f"⚠️ Could not enqueue fetch_products_task for {client.email}: {e}")
    finally:
        db.close()


@celery.task(name="send_reminders_after_one_month_task")
def send_reminders_after_one_month_task():
    
    db = SessionLocal()
    try:
        send_whatsapp_message_after_one_month(db)
    except Exception as e:
        print(f"[ERROR] Failed to send reminders: {e}")
    finally:
        db.close()

@celery.task(name="send_forecast_messages_to_low_churn_task")
def send_forecast_messages_to_low_churn_task():
    
    db = SessionLocal()
    try:
        todays_forecasts = helper_function_to_sending_message_to_low_churn_risk_customers(db)
        if todays_forecasts.empty:
            print("📭 No forecasted purchases today.")
            return
        for _, row in todays_forecasts.iterrows():
            phone_number = row["phone"]
            customer_name = row["customer_name"]
            status_en, result_en = send_whatsapp_forecast_message(phone_number, customer_name, "en")
            print(f"[EN] Sent to {customer_name} ({phone_number}): {status_en} - {result_en}")
            status_ar, result_ar = send_whatsapp_forecast_message(phone_number, customer_name, "ar")
            print(f"[AR] Sent to {customer_name} ({phone_number}): {status_ar} - {result_ar}")
    except Exception as e:
        print(f"[ERROR] Failed to send forecast messages: {e}")
    finally:
        db.close()

@celery.task(name="send_dead_customers_messages")
def send_dead_customers_messages():

    db = SessionLocal()
    results = []

    try:
        dead_customers = function_get_dead_customers(db)
        for customer in dead_customers:
            phone = customer.get("phone")
            if not phone:
                results.append({"customer_id": customer["customer_id"], "status": "Failed - No phone"})
                continue
            customer_results = {"customer_id": customer["customer_id"], "statuses": {}}
            for lang in ["en", "ar"]:
                try:
                    status_code, resp = send_whatsapp_dead_customer_message(
                        phone_number=phone,
                        customer_name=customer["customer_name"],
                        language=lang,
                    )
                    customer_results["statuses"][lang] = "Success" if status_code == 200 else f"Failed - {resp}"
                except Exception as e:
                    customer_results["statuses"][lang] = f"Failed - {str(e)}"
            results.append(customer_results)
    finally:
        db.close()
    return results

celery.conf.beat_schedule = {
    # 🔁 Fetch WooCommerce orders every 1 minutes
    # "fetch-orders-every-1-mins": {
    #     "task": "fetch_orders_task",
    #     "schedule": crontab(minute="*"),
    # },

     "fetch-orders-for-active-clients-every-1-min": {
        "task": "fetch_all_clients_orders_task",
        "schedule": crontab(minute="*"),  # Every minute
        "options": {
            "expires": 50,  # Expire task if not executed within 50 seconds
        }
    },

    # 🛒 Fetch WooCommerce products for active clients every 2 hours
    "fetch-products-for-active-clients-every-2-hours": {
        "task": "fetch_all_clients_products_task",
        "schedule": crontab(minute=0, hour="*/2"),
        "options": {
            "expires": 3500,  # expires ~1 hour
        }
    },

    # 📲 Send WhatsApp messages daily at 10 AM (if re-enabled)
    # "send-whatsapp-daily": {
    #     "task": "send_whatsapp_broadcast",
    #     "schedule": crontab(hour=10, minute=0),
    # },

    # 🔁 Run reorder prediction and message customers daily at 9 AM UTC
    # "send-reorder-prediction-daily": {
    #     "task": "predict_customers_task",
    #     "schedule": crontab(hour=9, minute=0),
    # },

    # sending message after one month from the order date
    #   "send-whatsapp-after-one-month":{
    #     "task": "send_reminders_after_one_month_task",
    #     "schedule": crontab(hour=10, minute=0)
    #   },
    #   # sending message after one month from the order date
    #   "send-whatsapp-to-low-churn-customers":{
    #     "task": "send_forecast_messages_to_low_churn_task",
    #     "schedule": crontab(hour=10, minute=0)
    #   }
    
    # 📲 Send WhatsApp messages to DEAD customers once a month
    # "send-dead-customers-messages-monthly": {
    #     "task": "send_dead_customers_messages",
    #     "schedule": crontab(minute=0, hour=10, day_of_month="1"),
    # },

}

