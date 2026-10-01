# Pasale Dai Collections

> **AI-powered conversational clothing store for Nepal --- Discord
> commerce, eSewa payments, automated invoicing, and lightweight
> operations management.**

Pasale Dai  is an autonomous e-commerce platform designed for
small-to-medium retail businesses in Nepal. Customers can browse
products, ask questions, build multi-item carts, complete payment
through **eSewa ePay v2**, and receive their invoice directly through
Discord.

The platform deliberately separates **AI reasoning from authoritative
business logic**:

-   The AI behaves like a conversational salesperson.
-   The backend remains the source of truth for prices, stock, orders,
    and payments.
-   Payment completion is verified server-to-server with eSewa.
-   Inventory changes happen atomically through backend-controlled order
    transitions.
-   PDF invoices are generated automatically after successful order
    confirmation.

------------------------------------------------------------------------

## Features

### 🤖 Conversational Sales Agent

-   Discord-based customer interaction.
-   Natural-language product discovery and purchase intent.
-   Powered by Google Gemini through its REST API.
-   Strictly grounded in the product catalog.
-   Supports multi-item requests such as:
    -   `I want 2 black hoodies and 1 denim jacket`
-   Extracts useful checkout information such as:
    -   Customer name
    -   Phone number
    -   Delivery address
    -   Location information
-   Avoids repeatedly sending product images once the customer has
    progressed toward checkout.
-   Isolated conversation memory per Discord user.

### 🛒 Multi-Item Cart & Order Management

-   Backend-authoritative pricing.
-   Multi-item cart support.
-   Dedicated `order_items` records.
-   Stock validation before order creation.
-   Atomic stock reduction during order confirmation.
-   Abandoned unpaid checkout cleanup.
-   Strict order lifecycle state machine.

### 💳 eSewa ePay v2

-   Official eSewa ePay v2 payment flow.
-   HMAC-SHA256 checkout signatures.
-   Base64-encoded signature generation.
-   Auto-submitting checkout form for POST-only eSewa endpoints.
-   Server-to-server transaction verification.
-   Payment callbacks are never trusted without gateway verification.
-   Supports test and production environments.

### 🧾 Automated PDF Invoices

-   Generated using ReportLab.
-   Multi-item line-item breakdown.
-   Customer and delivery details.
-   Payment information.
-   Business metadata.
-   Invoice number generation.
-   Automatically sent to the customer through Discord.

### 📊 Administrative Dashboard

Minimalist Flask-based operations console featuring:

-   Gross revenue KPI
-   Pending fulfillment
-   Completed orders
-   Low-stock alerts
-   Order tracking
-   Order status management
-   Customer/contact information
-   eSewa transaction audit information
-   Inventory management
-   Product visibility controls
-   Slide-over order details

------------------------------------------------------------------------

# Architecture

The system follows a strict principle:

> **AI is the interface. The backend is the authority.**

``` text
┌─────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER LAYER                              │
│                         Discord Interface                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ROUTING & STATE LAYER                           │
│   Conversation Memory       Product Catalog / Stock Source of Truth │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AI REASONING ENGINE                             │
│                  Google Gemini REST API                             │
│       Structured JSON Actions + Entity Extraction                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  BUSINESS LOGIC AUTHORITY                            │
│       Cart • Orders • Pricing • Stock • State Machine               │
└───────────────┬──────────────────┬──────────────────┬────────────────┘
                │                  │                  │
                ▼                  ▼                  ▼
       ┌────────────────┐ ┌────────────────┐ ┌────────────────────┐
       │ SQLite Database│ │ eSewa Gateway  │ │ Invoice Generator  │
       │                │ │   ePay v2      │ │     ReportLab      │
       └────────────────┘ └────────────────┘ └────────────────────┘
                ▲
                │
┌───────────────┴─────────────────────────────────────────────────────┐
│                    ADMINISTRATIVE INTERFACE                         │
│                    Flask Operations Console                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Architectural Principles

### 1. AI as Interface, Backend as Authority

The Gemini agent does not directly control:

-   Product prices
-   Inventory
-   Payment status
-   Order totals
-   Stock deductions

Instead, it produces structured proposals/actions that the backend
validates against authoritative database records.

### 2. Strict Order State Machine

Orders are expected to move through controlled states:

``` text
PENDING
   │
   ▼
PAYMENT_PENDING
   │
   ▼
PAID
   │
   ▼
CONFIRMED
   │
   ▼
PROCESSING
   │
   ▼
SHIPPED
   │
   ▼
DELIVERED
```

Orders may also transition to:

``` text
CANCELLED
```

according to backend validation rules.

### 3. Idempotent Payment Verification

A successful browser redirect is **not** treated as proof of payment.

The backend:

1.  Receives the eSewa response.
2.  Decodes the transaction payload.
3.  Checks the relevant order/payment information.
4.  Performs server-to-server transaction verification with eSewa.
5.  Updates payment/order state only after authoritative verification.

### 4. Isolated Conversation Context

Every Discord user has an independent conversation context.

This prevents one customer's:

-   Cart information
-   Address
-   Phone number
-   Product preferences
-   Conversation history

from leaking into another customer's session.

------------------------------------------------------------------------

# Technology Stack

  Component          Technology
  ------------------ --------------------------------
  Backend API        Python 3.10+, FastAPI, Uvicorn
  Discord Bot        discord.py 2.3+
  AI                 Google Gemini REST API
  HTTP Client        HTTPX
  Database           SQLite3
  Validation         Pydantic v2
  Configuration      Pydantic Settings
  Payments           eSewa ePay v2
  Cryptography       HMAC-SHA256
  PDF Generation     ReportLab 4.1+
  Image Processing   Pillow 10.2+
  Admin Console      Flask 3.0+
  Templates          Jinja2
  Frontend           Vanilla CSS / JavaScript

------------------------------------------------------------------------

# Project Structure

``` text
pasale-ai/
│
├── app/
│   ├── config.py
│   ├── main.py
│   │
│   ├── database/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repositories.py
│   │
│   ├── products/
│   │   ├── catalog.py
│   │   └── service.py
│   │
│   ├── memory/
│   │   ├── schemas.py
│   │   └── manager.py
│   │
│   ├── ai/
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   └── gemini.py
│   │
│   ├── payments/
│   │   ├── schemas.py
│   │   └── esewa.py
│   │
│   ├── orders/
│   │   ├── schemas.py
│   │   └── service.py
│   │
│   ├── invoices/
│   │   └── generator.py
│   │
│   ├── api/
│   │   └── routes.py
│   │
│   └── bot/
│       └── discord_bot.py
│
├── data/
│   └── store.db
│
├── flask/
│   ├── app.py
│   ├── config.py
│   ├── db.py
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── dashboard.js
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── payments.html
│       └── inventory.html
│
├── products/
│   ├── black-hoodie.png
│   ├── blue-shirt.png
│   ├── denim-jacket.png
│   └── white-tshirt.png
│
├── invoices/
│
├── memory/
│
├── .env.example
├── requirements.txt
├── run.py
└── README.md
```

------------------------------------------------------------------------

# Requirements

Before running the project, install:

-   Python **3.10+**
-   Git
-   A Discord Developer account and bot token
-   A Google Gemini API key
-   eSewa merchant credentials for production payments
-   A publicly reachable HTTPS URL for payment callbacks in environments
    where eSewa cannot reach localhost

------------------------------------------------------------------------

# Installation

## 1. Clone the repository

``` bash
git clone https://github.com/your-username/pasale-ai.git
cd pasale-ai
```

## 2. Create a virtual environment

### Linux / macOS

``` bash
python -m venv .venv
source .venv/bin/activate
```

### Windows

``` powershell
python -m venv .venv
.venv\Scripts\activate
```

## 3. Install dependencies

``` bash
pip install -r requirements.txt
```

If Flask is not included in your dependency file:

``` bash
pip install flask
```

------------------------------------------------------------------------

# Environment Configuration

Create the environment file:

``` bash
cp .env.example .env
```

On Windows, copy the file manually if `cp` is unavailable.

Example configuration:

``` env
# AI Service
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token

# eSewa ePay v2
ESEWA_PRODUCT_CODE=EPAYTEST
ESEWA_SECRET_KEY=your_esewa_secret_key
ESEWA_PAYMENT_URL=https://rc-epay.esewa.com.np/api/epay/main/v2/form
ESEWA_VERIFY_URL=https://rc-epay.esewa.com.np/api/epay/transaction/status/

# Application
BASE_URL=http://localhost:8000
DATABASE_URL=sqlite:///./data/store.db
MEMORY_MESSAGE_LIMIT=15

# Admin Dashboard
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_password
SECRET_KEY=generate_a_secure_random_secret
```

> **Security:** Never commit `.env` to Git. Production secrets should be
> stored using your deployment platform's secret/environment-variable
> system.

For production eSewa credentials and endpoints, use the values supplied
by eSewa for your merchant account and environment.

------------------------------------------------------------------------

# Running the Application

## Start FastAPI + Discord Bot

From the project root:

``` bash
python run.py
```

The runner is responsible for starting the core application components,
including:

-   SQLite initialization
-   Product catalog verification
-   FastAPI server
-   Discord bot

The API is available at:

``` text
http://0.0.0.0:8000
```

## Start the Admin Dashboard

Open another terminal and activate the virtual environment.

Then:

``` bash
python flask/app.py
```

Open:

``` text
http://127.0.0.1:5000
```

Log in with the credentials configured in `.env`.

------------------------------------------------------------------------

# Payment Flow

Pasale Dai Collections uses eSewa ePay v2 as the payment gateway.

``` text
Customer
   │
   │ Purchase through Discord
   ▼
Discord Bot
   │
   │ Request authoritative product/cart information
   ▼
FastAPI Backend
   │
   │ Calculate total from DB
   │ Create order
   │ Generate signed payment payload
   ▼
/checkout/<order_number>
   │
   │ Auto-submitting POST
   ▼
eSewa ePay v2
   │
   │ Customer completes payment
   ▼
eSewa Response
   │
   ▼
FastAPI Payment Callback
   │
   │ Server-to-server verification
   ▼
eSewa Verification API
   │
   │ COMPLETE / valid transaction
   ▼
Order marked PAID
   │
   ▼
Customer provides delivery information
   │
   ▼
Backend finalization
   │
   ├── Atomic stock update
   ├── Order confirmation
   └── PDF invoice generation
   │
   ▼
Discord
   │
   ├── Confirmation message
   └── PDF invoice
```

------------------------------------------------------------------------

# eSewa Signature

The checkout request uses an HMAC-SHA256 signature derived from the
required payment fields.

The signing message follows the eSewa ePay v2 specification, using:

``` text
total_amount
transaction_uuid
product_code
```

The generated HMAC digest is Base64 encoded before being included in the
payment request.

The merchant secret key must remain server-side and must never be
exposed to:

-   Discord users
-   Browser JavaScript
-   AI prompts
-   Client-side HTML
-   Public repositories

------------------------------------------------------------------------

# Local Payment Testing

eSewa cannot generally reach a private localhost callback directly.

For local development, expose the FastAPI application through a public
HTTPS tunnel such as:

-   Cloudflare Tunnel
-   ngrok
-   Microsoft Dev Tunnels

Then configure:

``` env
BASE_URL=https://your-public-domain.example
```

The callback URL generated by the application should therefore be
reachable from the public internet.

------------------------------------------------------------------------

# Purchase Lifecycle

## 1. Customer Intent

The customer says something like:

``` text
I want 2 black hoodies and one denim jacket.
```

The AI identifies the requested products and quantities.

## 2. Backend Validation

The backend independently checks:

-   Product existence
-   Product availability
-   Current price
-   Requested quantity
-   Cart contents

The AI cannot override these values.

## 3. Order Creation

The backend creates:

-   Customer record
-   Order record
-   Order item records
-   Payment information

The order enters the payment workflow.

## 4. Payment

The customer receives a checkout link.

The link points to:

``` text
/checkout/<order_number>
```

The backend renders an auto-submitting POST form to eSewa.

## 5. Verification

After payment, eSewa redirects the customer back to the application.

The application verifies the transaction directly with eSewa before
treating the payment as authoritative.

## 6. Delivery Information

The customer provides information such as:

``` text
My number is 98XXXXXXXX
and I live in Jhapa.
```

The AI extracts the relevant entities, while the backend validates and
persists them.

## 7. Finalization

After successful payment and sufficient delivery information:

-   Inventory is updated atomically.
-   Order status becomes `CONFIRMED`.
-   Invoice is generated.
-   Invoice is sent to the customer through Discord.

------------------------------------------------------------------------

# Conversation Memory

The system uses a dual-tier conversation memory architecture.

``` text
Incoming Message
       │
       ▼
┌───────────────────────┐
│ Recent Turn Cache     │
│ Last N conversation   │
│ messages              │
└───────────┬───────────┘
            │
            │ Exceeds configured limit
            ▼
┌───────────────────────┐
│ Memory Compactor      │
│ Summarizes older      │
│ conversation context  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Compact Summary       │
└───────────┬───────────┘
            │
            ▼
      Assembled AI Prompt
```

The default setting is:

``` env
MEMORY_MESSAGE_LIMIT=15
```

Conversation data is associated with the individual Discord user.

The implementation can maintain both:

-   SQLite conversation records
-   Per-user JSON memory snapshots

This provides persistent context while limiting the amount of raw
conversation sent to the AI model.

------------------------------------------------------------------------

# Database Schema

## customers

``` text
customers
├── id                  INTEGER PRIMARY KEY
├── discord_user_id     TEXT UNIQUE
├── discord_username    TEXT
├── name                TEXT
├── email               TEXT
├── phone               TEXT
├── address             TEXT
└── location_link       TEXT
```

## products

``` text
products
├── id                  TEXT PRIMARY KEY
├── sku                 TEXT UNIQUE
├── name                TEXT
├── description         TEXT
├── price               REAL
├── currency            TEXT DEFAULT 'NPR'
├── image_path          TEXT
├── stock               INTEGER
└── active              INTEGER DEFAULT 1
```

## orders

``` text
orders
├── id                       INTEGER PRIMARY KEY
├── order_number             TEXT UNIQUE
├── customer_id              INTEGER
├── product_id               TEXT
├── quantity                 INTEGER
├── total_amount             REAL
├── currency                 TEXT DEFAULT 'NPR'
├── status                   TEXT
├── delivery_phone           TEXT
├── delivery_address         TEXT
└── delivery_location_link   TEXT
```

## order_items

``` text
order_items
├── id              INTEGER PRIMARY KEY
├── order_id        INTEGER
├── product_id      TEXT
├── product_name    TEXT
├── quantity        INTEGER
├── unit_price      REAL
└── total_price     REAL
```

## payments

``` text
payments
├── id              INTEGER PRIMARY KEY
├── order_id        INTEGER
├── transaction_id  TEXT UNIQUE
├── product_code    TEXT
├── amount          REAL
├── currency        TEXT DEFAULT 'NPR'
├── status          TEXT
├── raw_response    TEXT
└── verified_at     TIMESTAMP
```

## invoices

``` text
invoices
├── id              INTEGER PRIMARY KEY
├── order_id        INTEGER UNIQUE
├── invoice_number  TEXT UNIQUE
└── file_path       TEXT
```

------------------------------------------------------------------------

# Security

Security-sensitive operations are intentionally kept outside the AI
layer.

### Tamper-resistant pricing

Prices are always retrieved from the database.

User-supplied or AI-generated prices are not trusted.

### HMAC-SHA256 payment signatures

eSewa payment payloads are signed using the merchant secret key.

### Authoritative payment verification

A browser redirect alone cannot mark an order as paid.

The backend performs gateway-side transaction verification before
updating payment state.

### SQL injection prevention

Database operations use parameterized SQL queries.

### Invoice path protection

Invoice access validates filenames and ensures the resolved path remains
within the intended invoice directory.

Expected invoice filenames follow the application's restricted pattern,
for example:

``` text
INV-ABC123.pdf
```

### Product image path protection

Product image resolution verifies that resolved paths remain within the
configured products directory.

### Secret management

Never commit:

``` text
.env
```

or production credentials to source control.

------------------------------------------------------------------------

# Admin Dashboard

The Flask dashboard provides a lightweight operational interface.

## Dashboard

Displays metrics such as:

-   Gross revenue
-   Pending fulfillment
-   Completed orders
-   Low-stock products

## Orders

Administrators can inspect:

-   Order number
-   Customer
-   Products
-   Quantities
-   Total amount
-   Delivery information
-   Payment verification data
-   Current fulfillment state

## Inventory

Administrators can:

-   View product stock
-   Update stock
-   Toggle product visibility
-   Review catalog availability

## Payments

The payment ledger provides transaction-oriented visibility into eSewa
payment records and verification status.

------------------------------------------------------------------------

# API / Application Responsibilities

The FastAPI application handles core application operations such as:

``` text
Health
Checkout
Payment callbacks
Payment verification
Order operations
Invoice access
```

The exact endpoints should be treated as implementation details defined
in:

``` text
app/api/routes.py
```

The Discord bot communicates with these backend services rather than
directly manipulating authoritative database state.



------------------------------------------------------------------------

## Gemini returns malformed JSON

The AI integration should treat model output as untrusted input.

The Gemini client includes structured action parsing and JSON
repair/validation logic. Any action still failing schema validation
should be rejected rather than executed.


------------------------------------------------------------------------

# Disclaimer

This README describes the intended architecture and implementation of
Pasale Dai Collections.

Payment integrations, API endpoints, credentials, gateway behavior,
Discord permissions, and third-party APIs can change over time. Always
verify current third-party technical requirements before deploying a
payment or production system.
