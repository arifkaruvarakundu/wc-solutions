from fastapi import APIRouter,FastAPI, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from database import get_db
from models import Client, Base
from utils.auth import get_current_client, hash_password, create_access_token, verify_password
from typing import Optional
from schemas import LoginRequest, RegisterRequest
from tasks.fetch_orders import fetch_orders_task
from datetime import datetime
from celery.result import AsyncResult
from celery.exceptions import OperationalError
import time

router = APIRouter()

@router.post("/register")
def register_client(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new client and trigger initial full order sync.
    """
    # --- Extract fields from request body ---
    email = request.email
    password = request.password
    client_name = request.client_name
    store_url = request.store_url
    consumer_key = request.consumer_key
    consumer_secret = request.consumer_secret

    # --- Check if user already exists ---
    existing = db.query(Client).filter(Client.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # --- Validate WooCommerce credentials are provided ---
    if not store_url or not consumer_key or not consumer_secret:
        raise HTTPException(
            status_code=400, 
            detail="WooCommerce credentials (store_url, consumer_key, consumer_secret) are required"
        )

    # --- Create new client ---
    new_client = Client(
        email=email,
        hashed_password=hash_password(password),
        client_name=client_name,
        store_url=store_url,
        is_logged_in=True,
        last_login_time=datetime.utcnow()
    )

    # --- Encrypt WooCommerce credentials (handled by model setters) ---
    new_client.consumer_key = consumer_key
    new_client.consumer_secret = consumer_secret

    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    # --- Create JWT token ---
    access_token = create_access_token(
        data={"sub": new_client.email, "user_id": new_client.id}
    )

    # Lazy import of the task to avoid early import-time side effects
    from celery_app import onboard_new_client_task

    # Retry enqueueing so transient broker/worker startup delays don't fail registration
    task_id = None
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            task = onboard_new_client_task.apply_async(kwargs={'client_id': new_client.id})
            task_id = task.id
            print(f"🚀 Triggered onboarding for client {new_client.email} (task_id={task_id})")
            break
        except OperationalError as e:
            # kombu/celery raises OperationalError on connection refused
            print(f"⚠️ Celery broker not ready (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(2)
            else:
                print("❌ Could not enqueue onboarding after retries; periodic sync will handle it.")
                task_id = None
        except Exception as e:
            # fallback catch-all (keeps registration from failing)
            print(f"⚠️ Could not enqueue onboarding for {new_client.email}: {e}")
            task_id = None
            break

    return {
        "message": "Client registered successfully",
        "client_id": new_client.id,
        "email": new_client.email,
        "access_token": access_token,
        "token_type": "bearer",
        "task_id": task_id,
    }

@router.get("/task-status/{task_id}")
def get_task_status(task_id: str):
    """
    Check Celery task progress.
    Returns one of: PENDING, STARTED, SUCCESS, FAILURE
    """
    result = AsyncResult(task_id)
    return {"task_id": task_id, "status": result.status}

@router.get("/sync-status/{email}")
def get_sync_status(email: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.email == email).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return {
        "sync_status": client.sync_status,
        "sync_complete": client.sync_status == "COMPLETE",
        "last_synced_at": client.last_synced_at
    }

@router.post("/login")
def login_client(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login client and trigger incremental order sync.
    """
    # --- Check if user exists ---
    user = db.query(Client).filter(Client.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # --- Update login status ---
    user.is_logged_in = True
    user.last_login_time = datetime.utcnow()
    db.commit()

    # --- Create JWT token ---
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )

    # --- Trigger background sync since last login ---
    # Only if credentials exist
    if user.store_url and user.consumer_key and user.consumer_secret:
        try:
            fetch_orders_task.delay(client_id=user.id, full_fetch=False)
            print(f"✅ Triggered incremental sync for client {user.id}")
        except Exception as e:
            # Log but don't fail login - periodic task will handle it
            print(f"⚠️ Could not enqueue fetch_orders_task: {e}")
            print(f"⚠️ Periodic task will handle sync for client {user.id}")
    else:
        print(f"⚠️ Client {user.id} missing WooCommerce credentials. Skipping sync.")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "client_name": user.client_name,
    }

@router.post("/logout")
def logout_client(
    current_user: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Logout client and update status.
    """
    current_user.is_logged_in = False
    db.commit()
    
    return {
        "message": "Logged out successfully",
        "email": current_user.email
    }