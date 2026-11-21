# Distributed Image Processing System

## 📌 Project Overview

The **Distributed Image Processing System** is a Python-based application that distributes image-processing tasks across multiple independent worker nodes.

Users can upload images, select an image-processing operation, and submit jobs through a simple user interface. A coordinator manages the jobs and distributes them among available workers.

The system aims to improve processing efficiency through parallel execution while demonstrating important distributed-systems concepts such as communication, scheduling, load balancing, and fault tolerance.

## 🎯 Project Objectives

- Process images using different image-processing techniques.
- Distribute jobs across multiple worker nodes.
- Implement a scheduling mechanism to assign jobs to workers.
- Detect worker failures and retry or reassign eligible jobs.
- Store job information and processing results.
- Evaluate performance using different numbers of workers.

## 🛠️ Technologies Used

- **Python** — Main programming language.
- **FastAPI** — API development and communication between services.
- **OpenCV** — Image-processing operations.
- **Streamlit** — User interface.
- **SQLite** — Job metadata and status storage.
- **Git & GitHub** — Version control and team collaboration.

## 🏗️ System Architecture

The system consists of the following components:

1. **Frontend:** Allows users to upload images, select operations, submit jobs, and view results.
2. **Coordinator:** Receives jobs, manages their statuses, and coordinates processing.
3. **Worker Nodes:** Process assigned images independently and return results.
4. **Scheduler:** Selects workers and distributes jobs among available nodes.
5. **Fault Tolerance:** Handles worker failures, timeouts, retries, and job reassignment.
6. **Database:** Stores job metadata, statuses, worker assignments, and result references.
7. **Image Processor:** Implements the image-processing algorithms using OpenCV.

## 🖼️ Supported Image Operations

The planned operations include:

- Grayscale conversion
- Gaussian blur
- Image thresholding
- Canny edge detection

## 📂 Project Structure

```text
distributed-image-processing/
│
├── app/
│   ├── coordinator.py
│   ├── worker.py
│   ├── processor.py
│   ├── scheduler.py
│   ├── fault_tolerance.py
│   ├── database.py
│   └── schemas.py
│
├── frontend/
│   └── app.py
│
├── data/
│   ├── inputs/
│   ├── outputs/
│   └── jobs.db
│
├── tests/
│   ├── test_worker.py
│   ├── test_scheduler.py
│   └── test_fault_tolerance.py
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd distributed-image-processing
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Check `.env.example` and create a `.env` file if required. Configure the coordinator address, worker settings, and other necessary options.

### 5. Run the application

The exact startup commands will be documented once the coordinator, worker, and frontend entry points are finalized.

The coordinator and each worker should run as separate processes or services to demonstrate distributed communication.

## 🔄 How It Works

1. The user uploads an image and selects an operation.
2. The frontend submits the processing request to the coordinator.
3. The coordinator creates a job and assigns it a unique ID.
4. The scheduler selects an available worker.
5. The worker processes the image and returns the result.
6. The coordinator updates the job status, and the result is made available to the user.
7. If a worker fails, the fault-tolerance component handles eligible retries or reassignment.
8. Job information and result references are stored for tracking and evaluation.

## 🧪 Testing and Performance Evaluation

The project will be tested to evaluate:

- Correctness of image-processing operations.
- Communication between the coordinator and workers.
- Job distribution across multiple workers.
- Recovery from worker failures.
- Processing time with one worker compared with multiple workers.
- Throughput and speedup under different workloads.

Performance results will be measured experimentally and documented with the test conditions.

## 👥 Team Responsibilities

The project is divided among five team members:

| Member | Responsibility |
|---|---|
| Member 1 | Coordinator and frontend integration |
| Member 2 | Worker services and image processing |
| Member 3 | Scheduling and load balancing |
| Member 4 | Fault tolerance and recovery |
| Member 5 | Database, testing, and performance evaluation |

## 📌 Project Status

**Status:** In Development

The team is implementing the core components, integrating the services, and testing the system incrementally.

## 🎓 Academic Context

This project is developed as part of a Distributed Systems course to demonstrate distributed processing, independent worker services, coordination, scheduling, fault tolerance, and performance evaluation.
