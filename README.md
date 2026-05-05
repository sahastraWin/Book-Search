# DataFlow Ingestion Engine

> A distributed, async data ingestion and workload management backend built with Java Spring Boot

[![Java](https://img.shields.io/badge/Java-17-orange?style=flat-square&logo=openjdk)](https://openjdk.org/projects/jdk/17/)
[![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.2.5-brightgreen?style=flat-square&logo=spring)](https://spring.io/projects/spring-boot)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-blue?style=flat-square&logo=mysql)](https://www.mysql.com/)
[![Maven](https://img.shields.io/badge/Maven-3.9-red?style=flat-square&logo=apachemaven)](https://maven.apache.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Features](#core-features)
4. [Design Patterns Used](#design-patterns-used)
5. [Database Schema](#database-schema)
6. [API Endpoints Reference](#api-endpoints-reference)
7. [Prerequisites and Setup](#prerequisites-and-setup)
8. [Running the Project](#running-the-project)
9. [Testing with Postman](#testing-with-postman)
10. [How to Deploy and Share](#how-to-deploy-and-share)
11. [Concurrency and Race Condition Prevention](#concurrency-and-race-condition-prevention)
12. [Interview Talking Points](#interview-talking-points)

---

## Project Overview

Analytics teams face a common challenge: reliably ingesting massive datasets without overwhelming the system or losing records. This engine solves that with:

- **Zero data loss** — every record is tracked, validated, and logged
- **Async processing** — HTTP requests return in milliseconds; heavy work runs on background threads
- **Backpressure** — rate limiting and queue caps prevent crashes under 1,000+ concurrent submissions
- **Full data lineage** — complete audit trail of every job's lifecycle, stored in MySQL

### Who This Is Built For

- Analytics engineers who need stable, governed data pipelines
- Teams moving from manual CSV uploads to automated, observable ingestion
- Architects who need to demonstrate operational efficiency

---

## Architecture Diagram

```
CLIENT (Postman / Frontend)
        |
        |  POST /api/v1/jobs (JSON body)
        v
EMBEDDED TOMCAT SERVER (port 8080)
  └── Spring DispatcherServlet
        |
        v
CONTROLLER LAYER
  ├── JobController        (request validation, rate limit headers, client IP)
  └── MetricsController   (/job-efficiency, /system-health, /jobs-over-time)
        |
        v
SERVICE LAYER
  ├── JobService           (submit, get status, cancel)
  ├── MetricsService       (KPI queries, health check, time-range)
  ├── RateLimiterService   (ConcurrentMap, AtomicInteger, sliding window)
  └── JobProcessingService (@Async — fire-and-forget)
        |  Runs on background ThreadPool (DataFlow-Worker-N)
        |  • Parse via Strategy Pattern
        |  • Validate records
        |  • Update DB with progress
        |  • Publish events via Observer Pattern
        |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
STRATEGY LAYER      OBSERVER LAYER      THREAD POOL (AsyncConfig)
CsvStrategy         JobCompletionLogger  Core:  5 threads
JsonStrategy        (writes audit logs)  Max:  20 threads
(via Factory)       JobNotification      Queue: 500 jobs
                    (console/email/slack)
        |
        v
MYSQL DATABASE
  ├── ingestion_jobs  (id, job_name, data_type, status, client_id,
  │                    total_records, processed_records, failed_records,
  │                    submitted_at, started_at, completed_at)
  └── job_logs        (id, job_id FK, log_level, message, stage,
                       record_count, created_at)
```

---

## Core Features

### 1. Asynchronous Job Management

- Clients submit jobs via REST API and **immediately receive a Job ID** (response in under 50ms)
- Heavy processing runs on a **dedicated background thread pool**
- Clients poll `GET /api/v1/jobs/{id}` to check progress

### 2. Workload Throttling

- **Rate limiting**: Max 100 requests/minute per client (configurable)
- **Thread pool backpressure**: Queue capacity of 500 jobs; excess triggers CallerRunsPolicy
- **Standard HTTP headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 3. Data Governance and Lineage

- Every job event (PENDING → RUNNING → COMPLETED) is logged with a timestamp
- Per-record validation failures are logged with the specific reason
- Full audit trail queryable via `GET /api/v1/jobs/{id}/logs`

### 4. Analytics Aggregation Endpoints

- `GET /api/v1/metrics/job-efficiency` — KPIs for an executive dashboard
- `GET /api/v1/metrics/system-health` — JVM, queue depth, health status
- `GET /api/v1/metrics/jobs-over-time` — time-windowed trend data

---

## Design Patterns Used

### Strategy Pattern — Parser Selection

```
IngestionStrategy  (Interface)
    + parse(content)
    + validate(record)
         |
         +--- CsvParserStrategy   (OpenCSV, RFC 4180 safe)
         +--- JsonParserStrategy  (Jackson, Array + NDJSON)

Selected by:
IngestionStrategyFactory
    Map<DataType, Strategy>
```

**Why?** Adding a new format (XML, Parquet) requires zero changes to existing code — just implement the interface and register it. This is the **Open/Closed Principle**.

---

### Observer Pattern — Event Notification

```
JobEventPublisher (Subject)
    List<JobEventListener>
         |
         |  notifies all
         +--- JobCompletionLogger   (priority=10, writes to DB)
         +--- JobNotificationObserver (priority=50, console/email/Slack)
         +--- (Future: MetricsUpdater, etc. — add without any code changes)
```

**Why?** When a job completes, multiple things need to happen (audit log, notification, metrics update). The Observer pattern lets us **add new reactions without modifying the core processing code**.

---

## Database Schema

```sql
-- TABLE: ingestion_jobs  (main job tracking table)
CREATE TABLE ingestion_jobs (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_name          VARCHAR(255) NOT NULL,
    data_type         ENUM('CSV', 'JSON') NOT NULL,
    status            ENUM('PENDING','RUNNING','COMPLETED','FAILED','CANCELLED') NOT NULL,
    client_id         VARCHAR(100),
    total_records     INT DEFAULT 0,
    processed_records INT DEFAULT 0,
    failed_records    INT DEFAULT 0,
    error_message     TEXT,
    priority          INT DEFAULT 1,
    submitted_at      DATETIME NOT NULL,
    started_at        DATETIME,
    completed_at      DATETIME,
    last_updated_at   DATETIME,

    INDEX idx_status       (status),
    INDEX idx_submitted_at (submitted_at),
    INDEX idx_client_id    (client_id)
);

-- TABLE: job_logs  (data lineage / audit trail)
CREATE TABLE job_logs (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_id       BIGINT NOT NULL,
    log_level    ENUM('INFO','WARN','ERROR','DEBUG') NOT NULL,
    message      TEXT NOT NULL,
    stage        VARCHAR(50),
    record_count INT,
    created_at   DATETIME NOT NULL,

    FOREIGN KEY (job_id) REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    INDEX idx_job_id_created (job_id, created_at)
);
```

### Job Lifecycle State Machine

```
PENDING  -->  RUNNING  -->  COMPLETED  (terminal)
                    \
                     -->  FAILED      (terminal)

From PENDING only:
PENDING  -->  CANCELLED               (terminal)
```

---

## API Endpoints Reference

### Job Management `/api/v1/jobs`

| Method | Endpoint | Description | HTTP Status |
|--------|----------|-------------|-------------|
| POST | `/api/v1/jobs` | Submit a new ingestion job | 202 Accepted |
| GET | `/api/v1/jobs` | List all jobs (optional `?status=PENDING`) | 200 OK |
| GET | `/api/v1/jobs/{id}` | Get specific job status | 200 OK |
| DELETE | `/api/v1/jobs/{id}` | Cancel a pending job | 200 OK |
| GET | `/api/v1/jobs/{id}/logs` | Get audit trail for a job | 200 OK |

### Metrics `/api/v1/metrics`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/metrics/job-efficiency` | KPIs: success rate, throughput |
| GET | `/api/v1/metrics/system-health` | Queue depth, JVM, health status |
| GET | `/api/v1/metrics/jobs-over-time` | Time-windowed job summary |
| GET | `/api/v1/metrics/summary` | Combined dashboard snapshot |

### Spring Actuator (built-in monitoring)

| Endpoint | Description |
|----------|-------------|
| GET `/actuator/health` | DB connectivity, app status |
| GET `/actuator/metrics` | JVM metrics (memory, threads, HTTP) |

---

## Prerequisites and Setup

### 1. Java 17 (JDK)

```bash
# Check if installed:
java -version
# Expected: openjdk version "17.x.x"

# Install if missing:
# Windows: https://adoptium.net/
# Mac:     brew install openjdk@17
# Ubuntu:  sudo apt install openjdk-17-jdk
```

### 2. Apache Maven

```bash
# Check if installed:
mvn -version
# Expected: Apache Maven 3.x.x

# Install if missing:
# Windows: https://maven.apache.org/download.cgi
# Mac:     brew install maven
# Ubuntu:  sudo apt install maven
```

### 3. MySQL 8.0

```bash
# Check if installed:
mysql --version

# Install if missing:
# Windows: https://dev.mysql.com/downloads/installer/
# Mac:     brew install mysql && brew services start mysql
# Ubuntu:  sudo apt install mysql-server && sudo systemctl start mysql
```

---

## Running the Project

### Step 1 — Create the MySQL Database

```bash
# Open MySQL shell:
mysql -u root -p

# Inside the shell:
CREATE DATABASE dataflow_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SHOW DATABASES;
EXIT;
```

### Step 2 — Clone or Download the Project

```bash
cd dataflow-engine

# Verify structure:
ls
# Should show: pom.xml  src/  logs/
```

### Step 3 — Configure the Database Connection

Open `src/main/resources/application.properties` and update:

```properties
spring.datasource.username=root
spring.datasource.password=YOUR_PASSWORD_HERE
```

> If your MySQL root password is empty, use: `spring.datasource.password=`

### Step 4 — Build the Project

```bash
mvn clean install -DskipTests
# Expected output: [INFO] BUILD SUCCESS
```

> `-DskipTests` skips tests during first build. Run `mvn test` separately.

### Step 5 — Run the Application

```bash
mvn spring-boot:run
```

You should see in the console:

```
╔══════════════════════════════════════════════════╗
║     DataFlow Ingestion Engine - STARTED          ║
║     API Base: http://localhost:8080/api/v1        ║
║     Health:   http://localhost:8080/actuator/health║
╚══════════════════════════════════════════════════╝
```

### Step 6 — Verify It's Running

```
GET http://localhost:8080/actuator/health
```

Expected response:

```
{
  "status": "UP",
  "components": {
    "db": { "status": "UP" },
    "diskSpace": { "status": "UP" }
  }
}
```

---

## Testing with Postman

Download Postman from: https://www.postman.com/downloads/

### Test 1 — Submit a CSV Job

- **Method:** POST
- **URL:** `http://localhost:8080/api/v1/jobs`
- **Header:** `Content-Type: application/json`
- **Body:**

```
{
  "jobName": "Q4-Sales-CSV-Test",
  "dataType": "CSV",
  "rawContent": "transaction_id,product_id,customer_id,price,quantity,category\nTXN001,PROD_A,CUST_001,29.99,2,Electronics\nTXN002,PROD_B,CUST_002,15.00,1,Books\nTXN003,PROD_C,CUST_003,49.99,3,Clothing\nTXN004,PROD_D,CUST_004,bad_price,1,Toys",
  "priority": 1
}
```

Expected response (202 Accepted):

```
{
  "jobId": 1,
  "jobName": "Q4-Sales-CSV-Test",
  "status": "PENDING",
  "message": "Job accepted and queued for processing. Use the jobId to track status.",
  "submittedAt": "2024-01-15T10:30:00"
}
```

---

### Test 2 — Check Job Status

- **Method:** GET
- **URL:** `http://localhost:8080/api/v1/jobs/1`

Expected response:

```
{
  "jobId": 1,
  "jobName": "Q4-Sales-CSV-Test",
  "status": "COMPLETED",
  "totalRecords": 4,
  "processedRecords": 3,
  "failedRecords": 1,
  "successRate": 75.0,
  "durationSeconds": 2
}
```

---

### Test 3 — Submit a JSON Job

- **Method:** POST
- **URL:** `http://localhost:8080/api/v1/jobs`
- **Body:**

```
{
  "jobName": "Product-Inventory-JSON",
  "dataType": "JSON",
  "rawContent": "[{\"transaction_id\":\"T001\",\"product_id\":\"P001\",\"customer_id\":\"C001\",\"price\":29.99,\"quantity\":5},{\"transaction_id\":\"T002\",\"product_id\":\"P002\",\"customer_id\":\"C002\",\"price\":15.00,\"quantity\":2}]"
}
```

---

### Test 4 — View Audit Trail / Lineage

- **Method:** GET
- **URL:** `http://localhost:8080/api/v1/jobs/1/logs`

Expected response:

```
[
  { "logLevel": "INFO", "message": "Job submitted and queued", "stage": "LIFECYCLE" },
  { "logLevel": "INFO", "message": "Parsing complete: 4 records detected in CSV payload", "stage": "PARSING" },
  { "logLevel": "WARN", "message": "Record 4 validation failed: Price is not a valid number: bad_price", "stage": "VALIDATION" },
  { "logLevel": "INFO", "message": "Job completed: 3/4 records processed (75.0% success)", "stage": "LIFECYCLE" }
]
```

---

### Test 5 — Analytics Dashboard

- **Method:** GET
- **URL:** `http://localhost:8080/api/v1/metrics/job-efficiency`

Expected response:

```
{
  "totalJobs": 5,
  "completedJobs": 4,
  "failedJobs": 0,
  "pendingJobs": 1,
  "overallSuccessRate": 100.0,
  "averageProcessingRatePerSecond": 2500.5,
  "totalRecordsProcessed": 10420
}
```

---

### Test 6 — System Health Check

- **Method:** GET
- **URL:** `http://localhost:8080/api/v1/metrics/system-health`

Expected response:

```
{
  "healthStatus": "HEALTHY",
  "queueDepth": 0,
  "activeJobs": 0,
  "jvmUsedMemoryMb": 128,
  "jvmMaxMemoryMb": 512,
  "jvmMemoryUsagePercent": 25.0,
  "activeThreadCount": 18
}
```

---

### Test 7 — Trigger Rate Limiting

Submit 10+ requests quickly using Postman Runner (Collection Runner → run Test 1 → iterations: 15). Around request 11 you will receive:

```
HTTP 429 Too Many Requests
{
  "status": 429,
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Limit: 100/min. Resets in 45s."
}
```

---

## How to Deploy and Share

### Option A — Share the JAR File (Simplest)

```bash
# Build the JAR:
mvn clean package -DskipTests

# JAR is created at: target/engine-1.0.0.jar

# Anyone with Java 17 can run it:
java -jar engine-1.0.0.jar
```

Share the JAR alongside `application.properties`. The recipient only needs Java 17 — no Maven or IDE required.

---

### Option B — Deploy to Render.com (Free Cloud)

**Step 1:** Push to GitHub

```bash
git init
git add .
git commit -m "Initial DataFlow Engine"
git remote add origin https://github.com/YOUR_USERNAME/dataflow-engine.git
git push -u origin main
```

**Step 2:** Go to [render.com](https://render.com) → New → Web Service

**Step 3:** Configure:

```
Build Command: mvn clean package -DskipTests
Start Command: java -jar target/engine-1.0.0.jar
Environment:   Java 17
```

**Step 4:** Add environment variables in the Render dashboard:

```
SPRING_DATASOURCE_URL=jdbc:mysql://your-db-host/dataflow_db
SPRING_DATASOURCE_USERNAME=your-user
SPRING_DATASOURCE_PASSWORD=your-password
```

Use [PlanetScale](https://planetscale.com) or [Railway](https://railway.app) for a free MySQL database.

---

### Option C — Docker

Create a `Dockerfile` in the project root:

```dockerfile
FROM eclipse-temurin:17-jdk-alpine
WORKDIR /app
COPY target/engine-1.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

Build and run:

```bash
mvn clean package -DskipTests
docker build -t dataflow-engine .
docker run -p 8080:8080 dataflow-engine
```

---

## Concurrency and Race Condition Prevention

### The Problem: Multiple Threads Updating the Same Job

```
Thread A reads:  processedRecords = 500
Thread B reads:  processedRecords = 500   <-- stale read
Thread A writes: processedRecords = 501
Thread B writes: processedRecords = 501   <-- lost increment (should be 502)
```

### Solution: One Thread Per Job

```
Job Queue
  Job #1  -->  Thread 1
  Job #2  -->  Thread 2
  Job #3  -->  Thread 3
  Job #4  -->  Thread 4
```

Each job is dequeued exactly once. One worker thread owns one job for its entire lifetime. Two threads never process the same job simultaneously. This eliminates counter race conditions entirely.

### Database Consistency via @Transactional

```java
@Transactional
public void markJobAsCompleted(IngestionJob job) {
    job.setStatus(COMPLETED);
    job.setCompletedAt(LocalDateTime.now());
    jobRepository.save(job);      // if this fails,
    eventPublisher.publish(job);  // DB rolls back automatically
}
```

### Thread-Safe Rate Limiting

```java
// ConcurrentHashMap: segment-level locking, no global lock
ConcurrentHashMap<String, RequestWindow> clientWindows;

// AtomicInteger: single CPU instruction (CAS), no synchronized block
AtomicInteger requestCount;
requestCount.incrementAndGet();
```

---

## Interview Talking Points

**"Why did you build this?"**

> I noticed the focus on operational efficiency and workload management. To understand the challenges an analytics team faces — ingesting massive datasets reliably without overwhelming infrastructure — I built a backend engine that directly addresses those problems.

**On the Thread Pool Design:**

> Instead of creating a new thread per job (which would create thousands of threads under load and crash the JVM), I implemented a ThreadPoolTaskExecutor with 5 core threads, 20 maximum, and a 500-job queue. When the queue fills, CallerRunsPolicy kicks in — the HTTP request thread processes the job itself, which naturally slows inbound submissions. This is backpressure: the system communicates its saturation by slowing down the inbound flow.

**On Preventing Race Conditions:**

> Our architecture guarantees that only one worker thread ever processes a single job. The job queue acts as a distribution mechanism — once a job ID is dequeued, no other thread can claim it. Additionally, all database mutations go through @Transactional boundaries, ensuring atomicity even if the JVM crashes mid-operation.

**On the Strategy Pattern:**

> The Strategy Pattern lets us support multiple data formats without ever modifying the processing pipeline. Adding Parquet support tomorrow means implementing one interface and registering it — zero changes to the existing code. This is the Open/Closed Principle in action.

**On Data Governance:**

> Every state transition is persisted to the job_logs table with a timestamp, stage name, and record count. This creates a queryable lineage trail. If a job from 6 months ago processed incorrectly, we can replay its exact log to understand what validation rules failed and why. In regulated industries — finance, healthcare — this kind of audit trail is legally required.

---

## Project Structure

```
dataflow-engine/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/dataflow/engine/
│   │   │   ├── DataFlowEngineApplication.java
│   │   │   ├── config/
│   │   │   │   └── AsyncConfig.java
│   │   │   ├── controller/
│   │   │   │   ├── JobController.java
│   │   │   │   └── MetricsController.java
│   │   │   ├── dto/
│   │   │   ├── exception/
│   │   │   ├── model/
│   │   │   │   ├── IngestionJob.java
│   │   │   │   ├── JobLog.java
│   │   │   │   ├── JobStatus.java
│   │   │   │   └── DataType.java
│   │   │   ├── observer/
│   │   │   │   ├── JobEventListener.java
│   │   │   │   ├── JobEventPublisher.java
│   │   │   │   ├── JobCompletionLogger.java
│   │   │   │   └── JobNotificationObserver.java
│   │   │   ├── repository/
│   │   │   │   ├── IngestionJobRepository.java
│   │   │   │   └── JobLogRepository.java
│   │   │   ├── scheduler/
│   │   │   │   └── JobCleanupScheduler.java
│   │   │   └── service/
│   │   │       ├── JobService.java
│   │   │       ├── JobProcessingService.java
│   │   │       ├── MetricsService.java
│   │   │       ├── RateLimiterService.java
│   │   │       └── strategy/
│   │   │           ├── IngestionStrategy.java
│   │   │           ├── CsvParserStrategy.java
│   │   │           ├── JsonParserStrategy.java
│   │   │           └── IngestionStrategyFactory.java
│   │   └── resources/
│   │       └── application.properties
│   └── test/
│       └── java/com/dataflow/engine/
│           └── CsvParserStrategyTest.java
└── logs/
    └── dataflow-engine.log
```

---

## Configuration Reference

| Property | Default | Description |
|----------|---------|-------------|
| `server.port` | `8080` | HTTP port |
| `dataflow.async.core-pool-size` | `5` | Always-alive worker threads |
| `dataflow.async.max-pool-size` | `20` | Max threads under burst |
| `dataflow.async.queue-capacity` | `500` | Max queued jobs before backpressure |
| `dataflow.rate-limit.max-requests-per-minute` | `100` | Rate limit per client |
| `spring.jpa.hibernate.ddl-auto` | `update` | Schema management (use `validate` in prod) |

---

## Built With

- **Java 17** — Records, text blocks, switch expressions
- **Spring Boot 3.2.5** — Web, Data JPA, Validation, Actuator, Scheduling
- **MySQL 8.0** — Relational data store with indexed queries
- **HikariCP** — High-performance JDBC connection pool
- **OpenCSV** — RFC 4180 compliant CSV parsing
- **Jackson** — JSON serialization/deserialization
- **Lombok** — Boilerplate elimination
- **JUnit 5 + AssertJ** — Unit testing

---

*Built to demonstrate production-grade backend architecture principles: async processing, concurrency safety, data governance, and operational observability.*
