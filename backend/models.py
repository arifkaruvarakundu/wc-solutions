from sqlalchemy import ( Column, Integer, BigInteger, String, Float, ForeignKey, DateTime, Index, Text, Boolean)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from cryptography.fernet import Fernet
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy.orm import relationship

# ------------------------------
# 1️⃣ Load environment variables
# ------------------------------
ENV_FILE = os.getenv("ENV_FILE", ".env")
env_path = os.path.join(os.path.dirname(__file__), ENV_FILE)
load_dotenv(dotenv_path=env_path)

FERNET_KEY = os.getenv("FERNET_KEY")

if not FERNET_KEY:
    raise ValueError("FERNET_KEY not set in environment variables")

fernet = Fernet(FERNET_KEY)
Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)

    # WooCommerce-related fields (will store encrypted values)
    store_url = Column(String, nullable=True)
    _consumer_key = Column("consumer_key", String, nullable=True)
    _consumer_secret = Column("consumer_secret", String, nullable=True)

    user_type = Column(String, default="client")
    is_active = Column(Boolean, default=True)
    is_logged_in = Column(Boolean, default=False)
    last_login_time = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    sync_status = Column(String, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETE, FAILED
    orders_count = Column(Integer, default=0)

    # 🔗 Relationship to customers
    customers = relationship("Customer", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Client(email={self.email}, store_url={self.store_url})>"

    # --- Encryption-aware properties ---

    @property
    def consumer_key(self):
        """Return decrypted consumer key"""
        if self._consumer_key:
            return fernet.decrypt(self._consumer_key.encode()).decode()
        return None

    @consumer_key.setter
    def consumer_key(self, value):
        """Encrypt and store consumer key"""
        if value:
            self._consumer_key = fernet.encrypt(value.encode()).decode()
        else:
            self._consumer_key = None

    @property
    def consumer_secret(self):
        """Return decrypted consumer secret"""
        if self._consumer_secret:
            return fernet.decrypt(self._consumer_secret.encode()).decode()
        return None

    @consumer_secret.setter
    def consumer_secret(self, value):
        """Encrypt and store consumer secret"""
        if value:
            self._consumer_secret = fernet.encrypt(value.encode()).decode()
        else:
            self._consumer_secret = None

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, index=True, nullable=True)
    phone = Column(String, unique=True, index=True)
    # 🔗 Reference back to client
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    client = relationship("Client", back_populates="customers")
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    address = relationship("Address", back_populates="customer", uselist=False, cascade="all, delete-orphan")
    whatsapp_messages = relationship("WhatsAppMessage", back_populates="customer", cascade="all, delete-orphan")

class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    company = Column(String)
    address_1 = Column(String)
    address_2 = Column(String)
    city = Column(String)
    state = Column(String)
    postcode = Column(String)
    country = Column(String)
    customer = relationship("Customer", back_populates="address")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)  # internal DB id
    external_id = Column(BigInteger, unique=True, index=True, nullable=True)  # WooCommerce ID (previously `order_id`)
    order_key = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"))
    status = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, index=True, nullable=False)
    payment_method = Column(String, nullable=True)
    attribution_referrer = Column(String, nullable=True)
    session_pages = Column(Integer, nullable=True)
    session_count = Column(Integer, nullable=True)
    device_type = Column(String, nullable=True)
    customer = relationship("Customer", back_populates="orders", passive_deletes=True)
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(BigInteger, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    short_description = Column(Text, nullable=True)
    regular_price = Column(Float, nullable=True)
    sales_price = Column(Float, nullable=True)
    total_sales = Column(Integer, nullable=True)
    categories = Column(String, nullable=True)  # stringified list or JSON
    stock_status = Column(String, nullable=True)
    weight = Column(Float, nullable=True)
    date_created = Column(DateTime, nullable=True)
    date_modified = Column(DateTime, nullable=True)

    # ✅ Relationship back to OrderItem
    order_items = relationship("OrderItem", back_populates="product")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    product_id = Column(Integer, ForeignKey("products.external_id", ondelete="SET NULL"))  # ✅ This is essential
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    order = relationship("Order", back_populates="items", passive_deletes=True)
    
    # ✅ Relationship to Product
    product = relationship("Product", back_populates="order_items")

class SyncState(Base):
    __tablename__ = "sync_state"
    key = Column(String, primary_key=True)
    value = Column(String)

class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    direction = Column(String, nullable=False)  # "incoming" or "outgoing"
    message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=True)  # ✅ NEW: sent, delivered, read
    whatsapp_message_id = Column(String, nullable=True, unique=True)

    # 🔙 Relationship back to customer
    customer = relationship("Customer", back_populates="whatsapp_messages")

class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String, unique=True, index=True, nullable=False)
    category = Column(String(100))
    language = Column(String(10))
    status = Column(String(50))
    body = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def variables(self) -> list[str]:
        return re.findall(r"{{.*?}}", self.body or "")