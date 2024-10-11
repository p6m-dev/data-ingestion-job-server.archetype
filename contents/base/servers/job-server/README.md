# Task Manager

This is a Task Manager that create, claim, and manage tasks in a task queue using SQLAlchemy for database management.

## Getting Started

These instructions will help you set up and run the project on your local machine.

### Prerequisites

- POSTgresSQL database
- Python 3.6 or later
- pip package manager

### Database setup

1. Create a database
2. navigate to this project's root directory
3. run queries from database/task_queue.sql on database
4. open task_queue/main.py (this directory) and change database credentials in
    <pre>
    db_host = 'localhost'
    db_name = 'de-database'
    db_user = 'postgres'
    db_password = 'postgres'
    </pre>

### Installation



Create and activate a virtual environment:

Install project dependencies:

``` bash
 pip install -r requirements.txt 
```


### Running the Application

Start the application using uvicorn:

``` bash
uvicorn main:app --reload
```

The application will be accessible at http://127.0.0.1:8000.


### Documentation

Access the API documentation by opening your browser and navigating to:


```http://127.0.0.1:8000/docs```

Here, you can interact with the API endpoints using the interactive documentation provided by FastAPI.

API Endpoints

    PUT /put_task: Enqueues a new task in the task queue.

    POST /claim_task: Claims an unclaimed task from the task queue.

    PUT /task_completed: Marks a task as completed or failed.

Refer to the API documentation for detailed information on using these endpoints.
