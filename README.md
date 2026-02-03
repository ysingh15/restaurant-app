# Singh’s Kitchen – Cloud Restaurant Web Application

## Overview
Singh’s Kitchen is a cloud-based restaurant ordering web application developed for **SD Coursework (Submission 1)**.  
The system allows users to browse a menu, place orders, simulate payments, and view order history, while administrators manage menu items and sales summaries.

The project demonstrates the use of **cloud-native technologies**, **multiple databases**, **REST APIs**, **Cloud Functions**, **security mechanisms**, and **unit testing**.

---

## Key Features
- User registration and login with secure password hashing
- Menu browsing with category filtering
- Cart management and checkout with postcode validation
- Simulated card payment (no real transactions)
- Order history for users
- Admin CRUD operations for menu items
- Image uploads using Google Cloud Storage
- Order event logging using Firestore (NoSQL)
- Cloud Functions for receipt generation and daily sales summary
- Custom REST API endpoints

---

## Technology Stack
- **Backend:** Python, Flask  
- **Frontend:** Jinja2, Bootstrap  
- **SQL Database:** PostgreSQL (Cloud SQL)  
- **NoSQL Database:** Google Firestore (Native mode)  
- **Cloud Platform:** Google App Engine  
- **Storage:** Google Cloud Storage  
- **APIs:** Custom REST APIs and Google Cloud APIs  
- **Testing:** Pytest  
- **Version Control:** GitHub  

---

## REST API
- `GET /api/menu` – Returns menu items as JSON  
- `POST /api/menu` – Creates a new menu item  

---

## Databases
- **SQL:** Users, menu items, orders, and order items  
- **NoSQL (Firestore):** Order event logs with semi-structured data  

---

## Security
- Secure password hashing
- Session-based authentication
- Role-based access control (admin vs user)
- Server-side input validation
- Secure file upload handling
- Sensitive configuration managed using environment variables

---

## Deployment
The application is deployed on **Google App Engine** using `app.yaml`.  
Cloud SQL is used for relational data storage, Firestore for NoSQL logging, and Cloud Storage for image uploads.
To Deploy use gcloud app deploy

---

## Testing
Unit tests are implemented using **pytest**.  
A total of **7 successful tests** cover authentication, REST APIs, access control, and database operations.

To run tests:
```bash
pytest
