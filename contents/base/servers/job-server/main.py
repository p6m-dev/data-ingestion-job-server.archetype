import re
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Query, Form
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from utils import get_env_var, ErrorCode
from Logger import Logger, LogLevel
from database import get_db, TaskStatus, TaskType, TaskQueue
import requests

import hashlib
import time
import json

from md5 import MD5Generator

# TODO : import logging

#  Global scope variables initialization begin

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$"


host = get_env_var("HOST", DEFAULT_HOST)
port = int(get_env_var("PORT", DEFAULT_PORT))

#  Global scope variables initialization end

app = FastAPI(
    title="Task Queue API",
    version="1.0.0",
    description="APIs to manage a task queue",
)

# Create an instance of the Logger class
logger = Logger()

@app.get("/echo")
async def echo(message: str = Query(None, alias="message")):
    return {"message": message}


@app.get("/health/readiness")
def health_check():
    return {"status": "healthy"}


@app.put("/tasks")
def put_task(
    task_type: str,
    query: str,
    requested_by_user: str,
    notes: str = None,
    db: Session = Depends(get_db),
):
    """
    Enqueues a new task in the task queue.

    Args:
    - task_type (str): The type of the task.
    - query (str): The task query.
    - requested_by_user (str): The email of the user requesting the task.
    - notes (str, optional): Additional notes for the task.
    - db (Session): The SQLAlchemy database session.

    Returns:
    dict: A dictionary containing the status and message.
    """

    try:
        # Perform a regex check for a valid email format
        if not re.match(EMAIL_PATTERN, requested_by_user):
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "Invalid requester email format",
            }

        # Query the task_type_id
        task_type_db = db.query(TaskType).filter(TaskType.name == task_type).first()
        if not task_type_db:
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "Invalid task type",
            }

        # Query the "unclaimed" task status
        unclaimed_status = (
            db.query(TaskStatus).filter(TaskStatus.name == "unclaimed").first()
        )
        if not unclaimed_status:
            # TODO : add tp error log at every failure
            return {
                "status": False,
                "error_code": ErrorCode.NOT_FOUND.value["code"],
                "error_message": "Task status not found",
            }

        # encrypted_param = md5_hash(query)

        input_json = {query}  # Your JSON data
        keys_to_exclude = []  # List of keys to exclude
        delimiter = ","  # Your delimiter
        print("MD5")
        md5_gen = MD5Generator(input_json, keys_to_exclude, delimiter)

        (
            sorted_json,
            concatenated_str,
            trimmed_str,
            lowercase_str,
            encrypted_param,
        ) = md5_gen.process_json()
        print("MD5 code ", encrypted_param)
        epoch_time = str(int(time.time()))
        revision = epoch_time + "_" + encrypted_param

        # Create a new task in the queue
        new_task = TaskQueue(
            query=query,
            task_type_id=task_type_db.id,
            claimed_time=None,
            claimed_by_agent=None,
            task_status_id=unclaimed_status.id,
            message=None,
            completed_time=None,
            failed_time=None,
            requested_by_user=requested_by_user,
            notes=notes,
            object_storage_key_for_results=None,
            job_progress_metrics=None,
            parameter_checksum=encrypted_param,
            revision=revision,
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        print("sss ", new_task)

        return {"status": True, "message": "Task enqueued"}
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


@app.post("/tasks/claim")
def claim_task(task_type: str, agent_id: str, db: Session = Depends(get_db)):
    """
    Claims an unclaimed task of a specific type for a given agent.

    Args:
    - task_type (str): The type of the task to claim.
    - agent_id (str): The ID of the agent claiming the task.
    - db (Session): The SQLAlchemy database session.

    Returns:
    dict: A dictionary containing the status and data of the claimed task.
    """

    try:
        task_type_db = db.query(TaskType).filter(TaskType.name == task_type).first()
        if not task_type_db:
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "Invalid task type",
            }

        unclaimed_status = (
            db.query(TaskStatus).filter(TaskStatus.name == "unclaimed").first()
        )
        if not unclaimed_status:
            return {
                "status": False,
                "error_code": ErrorCode.NOT_FOUND.value["code"],
                "error_message": "Task status not found",
            }

        task_to_claim = (
            db.query(TaskQueue)
            .filter(
                TaskQueue.task_type_id == task_type_db.id,
                TaskQueue.task_status_id == unclaimed_status.id,
            )
            .order_by(TaskQueue.id)
            .first()
        )

        if not task_to_claim:
            return {
                "status": False,
                "error_code": ErrorCode.NOT_FOUND.value["code"],
                "error_message": "No unclaimed task found",
            }

        task_to_claim.task_status_id = (
            db.query(TaskStatus).filter(TaskStatus.name == "claimed").first().id
        )
        task_to_claim.claimed_by_agent = agent_id
        task_to_claim.claimed_time = datetime.now()
        db.commit()

        return {
            "status": True,
            "data": {
                "id": task_to_claim.id,
                "query": task_to_claim.query,
                "task_type_id": task_to_claim.task_type_id,
                "claimed_time": task_to_claim.claimed_time,
                "claimed_by_agent": task_to_claim.claimed_by_agent,
                "task_status_id": task_to_claim.task_status_id,
                "message": task_to_claim.message,
                "completed_time": task_to_claim.completed_time,
                "failed_time": task_to_claim.failed_time,
            },
        }
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


@app.get("/tasks")
def get_tasks(
    task_type: Optional[str] = None,
    task_status: Optional[str] = None,
    task_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieves tasks based on optional filters.

    Args:
    - task_type (str, optional): The type of tasks to retrieve.
    - task_status (str, optional): The status of tasks to retrieve.
    - task_id (int, optional): The ID of the specific task to retrieve.
    - db (Session): The SQLAlchemy database session.

    Returns:
    List[dict]: A list of dictionaries containing task information.
    """
    try:
        task_type_id = -1
        task_filter = []

        if task_type is not None:
            task_type_db = db.query(TaskType).filter(TaskType.name == task_type).first()
            if not task_type_db:
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "Invalid task type",
                }
            else:
                task_type_id = task_type_db.id
                task_filter.append(TaskQueue.task_type_id == task_type_id)

        if task_status is not None:
            task_status_db = (
                db.query(TaskStatus).filter(TaskStatus.name == task_status).first()
            )
            if not task_status_db:
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "Invalid task status",
                }
            else:
                task_status_id = task_status_db.id
                task_filter.append(TaskQueue.task_status_id == task_status_id)

        if task_id is not None:
            task_filter.append(TaskQueue.id == task_id)

        if not task_filter:
            # If no specific task type or task ID provided, retrieve all tasks
            tasks = db.query(TaskQueue).all()
        else:
            # Filter tasks based on provided criteria
            tasks = db.query(TaskQueue).filter(*task_filter).all()

        task_type_list = db.query(TaskType).all()

        task_status_list = db.query(TaskStatus).all()

        # Create a list of dictionaries with selected fields
        result = [
            {
                "id": task.id,
                "query": task.query,
                "task_type": get_task_type_name_by_id(
                    task_type_list, task.task_type_id
                ),
                "task_status": get_task_status_name_by_id(
                    task_status_list, task.task_status_id
                ),
                "requested_by_user": task.requested_by_user,
                "claimed_time": task.claimed_time,
                "claimed_by_agent": task.claimed_by_agent,
                "completed_time": task.completed_time,
                "failed_time": task.failed_time,
                "job_progress_metrics": task.job_progress_metrics,
                "object_storage_key_for_results": task.object_storage_key_for_results,
                "notes": task.notes,
            }
            for task in tasks
        ]

        return result
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


@app.get("/JobStatus")
def get_task_by_query(
    task_type: str = None,
    query: str = None,
    db: Session = Depends(get_db),
):
    """
    Retrieves tasks based on optional filters.

    Args:
    - task_type (str): The type of tasks to retrieve.
    - query (str): Query param of task to retrieve.
    - db (Session): The SQLAlchemy database session.

    Returns:
    List[dict]: A list of dictionaries containing task information.
    """
    try:
        task_type_id = -1
        task_filter = []

        # param_hash = md5_hash(query)

        input_json = {query}  # Your JSON data
        keys_to_exclude = []  # List of keys to exclude
        delimiter = ","  # Your delimiter

        md5_gen = MD5Generator(input_json, keys_to_exclude, delimiter)
        (
            sorted_json,
            concatenated_str,
            trimmed_str,
            lowercase_str,
            param_hash,
        ) = md5_gen.process_json()

        if task_type is None:
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "Invalid task type",
            }
        else:
            print("task type no None")
            task_type_db = db.query(TaskType).filter(TaskType.name == task_type).first()
            if not task_type_db:
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "Invalid task type",
                }
            else:
                task_type_id = task_type_db.id
                task_filter.append(TaskQueue.task_type_id == task_type_id)

        if query is None:
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "Invalid query",
            }

        task_filter.append(TaskQueue.parameter_checksum == param_hash)

        if not task_filter:
            # If no specific task type or task ID provided, retrieve all tasks
            tasks = db.query(TaskQueue).all()
        else:
            # Filter tasks based on provided criteria
            tasks = db.query(TaskQueue).filter(*task_filter).all()

        task_type_list = db.query(TaskType).all()

        task_status_list = db.query(TaskStatus).all()

        # Create a list of dictionaries with selected fields
        result = [
            {
                "id": task.id,
                "query": task.query,
                "revision": task.revision,
                "task_type": get_task_type_name_by_id(
                    task_type_list, task.task_type_id
                ),
                "task_status": get_task_status_name_by_id(
                    task_status_list, task.task_status_id
                ),
                "requested_by_user": task.requested_by_user,
                "claimed_time": task.claimed_time,
                "claimed_by_agent": task.claimed_by_agent,
                "completed_time": task.completed_time,
                "failed_time": task.failed_time,
                "job_progress_metrics": task.job_progress_metrics,
                "object_storage_key_for_results": task.object_storage_key_for_results,
                "notes": task.notes,
            }
            for task in tasks
        ]

        return result
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


@app.get("/DatasetDiscovery")
def get_task_by_revision(
    revision: str = None,
    db: Session = Depends(get_db),
):
    """
    Retrieves tasks based on optional filters.

    Args:
    - revision (str): revision param of task to retrieve.

    Returns:
    List[dict]: A list of dictionaries containing task information.
    """
    try:
        task_filter = []

        if revision is None:
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "Invalid revision id",
            }

        task_filter.append(TaskQueue.revision == revision)

        if not task_filter:
            # If no specific task type or task ID provided, retrieve all tasks
            tasks = db.query(TaskQueue).all()
        else:
            # Filter tasks based on provided criteria
            tasks = db.query(TaskQueue).filter(*task_filter).all()

        task_type_list = db.query(TaskType).all()

        task_status_list = db.query(TaskStatus).all()

        # # Create a list of dictionaries with selected fields
        # result = [
        #     {
        #         "id": task.id,
        #         "query": task.query,
        #         "revision": task.revision,
        #         "task_type": get_task_type_name_by_id(
        #             task_type_list, task.task_type_id
        #         ),
        #         "task_status": get_task_status_name_by_id(
        #             task_status_list, task.task_status_id
        #         ),
        #         "requested_by_user": task.requested_by_user,
        #         "claimed_time": task.claimed_time,
        #         "claimed_by_agent": task.claimed_by_agent,
        #         "completed_time": task.completed_time,
        #         "failed_time": task.failed_time,
        #         "job_progress_metrics": task.job_progress_metrics,
        #         "object_storage_key_for_results": task.object_storage_key_for_results,
        #         "notes": task.notes,
        #     }
        #     for task in tasks
        # ]

        # Create a list to store tasks with associated document content
        tasks_with_content = []

        task_type_list = db.query(TaskType).all()

        task_status_list = db.query(TaskStatus).all()

        # Step 2: Get document IDs for each completed task
        for task in tasks:
            task_id = task.id

            task_original_content = []
            task_text_content = []

            text_document_url = (
                f"http://34.220.33.50:8000/text-document/task/{task_id}/docs/"
            )
            # Include start_date and end_date parameters when calling the API
            doc_response = requests.get(
                text_document_url,
                # params={"start_date": start_date, "end_date": end_date},
                params={"start_date": "", "end_date": ""},
            )

            if doc_response.status_code == 200:
                doc_ids = doc_response.json().get("data", [])

                # Step 3: Get content for each document and add it to the task object
                task_text_content = []
                for doc_id in doc_ids:
                    text_metadata_url = (
                        f"http://34.220.33.50:8000/text-document/metadata/{doc_id}"
                    )
                    metadata_response = requests.get(text_metadata_url)

                    if metadata_response.status_code == 200:
                        text_metadata = (
                            metadata_response.json()
                            .get("data", {})
                            .get("file_metadata", {})
                        )
                    else:
                        text_metadata = {}

                    content_url = (
                        f"http://34.220.33.50:8000/text-document/content/{doc_id}"
                    )

                    # Include start_date and end_date parameters when calling the API
                    content_response = requests.get(
                        content_url,
                        # params={"start_date": start_date, "end_date": end_date},
                        params={"start_date": "", "end_date": ""},
                    )

                    if content_response.status_code == 200:
                        try:
                            # Try to parse the content as JSON
                            content_data = json.loads(content_response.text)
                            if (
                                "status" in content_data
                                and content_data["status"] != "false"
                            ):
                                content = content_data.get("content", "")
                            else:
                                content = "Status is false in JSON content"
                        except json.JSONDecodeError:
                            # If parsing as JSON fails, assume it's plain text
                            content = content_response.text
                    else:
                        content = f"Failed to fetch content for Document ID {doc_id}"

                    task_text_content.append(
                        {
                            "document_id": doc_id,
                            "metadata": text_metadata,
                            "content": content,
                        }
                    )
            original_document_url = (
                f"http://34.220.33.50:8000/original-document/task/{task_id}/docs/"
            )
            # Include start_date and end_date parameters when calling the API
            doc_response = requests.get(
                original_document_url,
                # params={"start_date": start_date, "end_date": end_date},
                params={"start_date": "", "end_date": ""},
            )

            if doc_response.status_code == 200:
                doc_ids = doc_response.json().get("data", [])

                # Step 3: Get content for each document and add it to the task object
                task_original_content = []
                for doc_id in doc_ids:
                    original_metadata_url = (
                        f"http://34.220.33.50:8000/original-document/metadata/{doc_id}"
                    )
                    metadata_response = requests.get(original_metadata_url)

                    if metadata_response.status_code == 200:
                        original_metadata = (
                            metadata_response.json()
                            .get("data", {})
                            .get("file_metadata", {})
                        )
                    else:
                        original_metadata = {}

                    content_url = (
                        f"http://34.220.33.50:8000/original-document/content/{doc_id}"
                    )

                    # # Include start_date and end_date parameters when calling the API
                    # content_response = requests.get(
                    #     content_url,
                    #     params={"start_date": start_date, "end_date": end_date},
                    # )
                    # Include start_date and end_date parameters when calling the API
                    content_response = requests.get(
                        content_url,
                        params={"start_date": "", "end_date": ""},
                    )

                    if content_response.status_code == 200:
                        try:
                            # Try to parse the content as JSON
                            content_data = json.loads(content_response.text)
                            if (
                                "status" in content_data
                                and content_data["status"] != "false"
                            ):
                                content = content_data.get("content", "")
                            else:
                                content = "Status is false in JSON content"
                        except json.JSONDecodeError:
                            # If parsing as JSON fails, assume it's plain text
                            content = content_response.text
                    else:
                        content = f"Failed to fetch content for Document ID {doc_id}"

                    task_original_content.append(
                        {
                            "document_id": doc_id,
                            "metadata": original_metadata,
                            "content": content,
                        }
                    )

            # Add the task with its associated document content to the list
            tasks_with_content.append(
                {
                    "task": {
                        "id": task.id,
                        "query": task.query,
                        "revision": task.revision,
                        "task_type": get_task_type_name_by_id(
                            task_type_list, task.task_type_id
                        ),
                        "task_status": get_task_status_name_by_id(
                            task_status_list, task.task_status_id
                        ),
                        "requested_by_user": task.requested_by_user,
                        "claimed_time": task.claimed_time,
                        "claimed_by_agent": task.claimed_by_agent,
                        "completed_time": task.completed_time,
                        "failed_time": task.failed_time,
                        "job_progress_metrics": task.job_progress_metrics,
                        "object_storage_key_for_results": task.object_storage_key_for_results,
                        "notes": task.notes,
                    },
                    "original_content": task_original_content,
                    "text_content": task_text_content,
                }
            )
        return tasks_with_content
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


@app.put("/tasks/complete")
def task_completed(
    task_id: int,
    success: bool,
    object_storage_key_for_results: Optional[str] = "",
    message: Optional[str] = "",
    db: Session = Depends(get_db),
):
    """
    Updates the status of a task to either completed or failed.

    Args:
    - task_id (int): The ID of the task to update.
    - success (bool): Whether the task was successful or not.
    - object_storage_key_for_results (str, optional): The key for storing results.
    - message (str, optional): Additional message regarding the task.
    - db (Session): The SQLAlchemy database session.

    Returns:
    dict: A dictionary containing the status and message.
    """
    try:
        if success and not object_storage_key_for_results:
            return {
                "status": False,
                "error_code": ErrorCode.GENERAL.value["code"],
                "error_message": "object_storage_key_for_results cannot be empty",
            }

        task_to_update = db.query(TaskQueue).filter(TaskQueue.id == task_id).first()
        if not task_to_update:
            return {
                "status": False,
                "error_code": ErrorCode.NOT_FOUND.value["code"],
                "error_message": "Task not found",
            }

        if success:
            task_to_update.task_status_id = (
                db.query(TaskStatus).filter(TaskStatus.name == "completed").first().id
            )
            task_to_update.object_storage_key_for_results = (
                object_storage_key_for_results
            )
            task_to_update.completed_time = datetime.now()
        else:
            task_to_update.task_status_id = (
                db.query(TaskStatus).filter(TaskStatus.name == "failed").first().id
            )
            task_to_update.failed_time = datetime.now()

        task_to_update.message = message
        db.commit()

        return {"status": True, "message": "Task status updated"}
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


@app.put("/tasks/metrics/{task_id}")
def update_job_progress_metrics(
    task_id: int, job_progress_metrics: dict, db: Session = Depends(get_db)
):
    """
    Updates the job progress metrics for a specific task.

    Args:
    - task_id (int): The ID of the task to update.
    - job_progress_metrics (dict): The updated job progress metrics.
    - db (Session): The SQLAlchemy database session.

    Returns:
    dict: A dictionary containing the status and message.
    """
    try:
        # Retrieve the task by ID
        task = db.query(TaskQueue).filter(TaskQueue.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Update the job_progress_metrics field with the provided data
        task.job_progress_metrics = job_progress_metrics

        # Commit the changes to the database
        db.commit()
        db.refresh(task)

        return {"status": True, "message": "Job progress metrics updated successfully"}
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


# TODO : use python black formatter


@app.get("/tasks/status")
def status(
    task_type: Optional[str] = "",
    task_status: Optional[str] = "",
    task_id: Optional[int] = None,
    query: Optional[str] = Query(None, description="Query filter"),
    db: Session = Depends(
        get_db
    ),  # Assuming you have a function to get the database session
):
    """
    Retrieves task status based on optional filters.

    Args:
    - task_type (str, optional): The type of tasks to retrieve.
    - task_status (str, optional): The status of tasks to retrieve.
    - task_id (int, optional): The ID of the specific task to retrieve.
    - query (str, optional): Additional query filter.
    - db (Session): The SQLAlchemy database session.

    Returns:
    Union[List[dict], dict]: Either a list of dictionaries containing task information or an error message.
    """
    try:
        if task_type:
            # Validate task_type
            if task_type and not isinstance(task_type, str):
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "task_type must be a string",
                }

            # Query the task_type_id
            task_type_db = db.query(TaskType).filter(TaskType.name == task_type).first()
            if not task_type_db:
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "Invalid task type",
                }

        if task_status:
            # Validate task_status
            if task_status and not isinstance(task_status, str):
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "task_status must be a string",
                }
            # Query the "unclaimed" task status
            task_status_db = (
                db.query(TaskStatus).filter(TaskStatus.name == task_status).first()
            )
            if not task_status_db:
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "invalid task status",
                }

        if task_id:
            # Validate task_id
            if task_id and not isinstance(task_id, int):
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "task_id must be an integer",
                }
            # Check if task_id exists in TaskQueue table
            task_in_db = db.query(TaskQueue).filter(TaskQueue.id == task_id).first()
            if not task_in_db:
                return {
                    "status": False,
                    "error_code": ErrorCode.GENERAL.value["code"],
                    "error_message": "Invalid task id",
                }

        if task_type:
            task_type_filter = f"?task_type={task_type}"
        else:
            task_type_filter = ""

        if task_status:
            if "?" in task_type_filter:
                task_type_filter += f"&task_status={task_status}"
            else:
                task_type_filter = f"?task_status={task_status}"

        if task_id:
            if "?" in task_type_filter:
                task_type_filter += f"&task_id={task_id}"
            else:
                task_type_filter = f"?task_id={task_id}"

        if query:
            if "?" in task_type_filter:
                task_type_filter += f"&query={query}"
            else:
                task_type_filter = f"?query={query}"

        # Step 1: Get completed tasks IDs by type (talkwalker)
        completed_tasks_url = f"http://127.0.0.1:8000/tasks{task_type_filter}"
        response = requests.get(completed_tasks_url)
        if response.status_code == 200:
            completed_tasks = response.json()

            # Create a list to store tasks with associated document content
            # tasks_with_content = []
            tasks = []

            # Step 2: Get document IDs for each completed task
            for task in completed_tasks:
                tasks.append(task)

            return tasks

        else:
            return {
                "status": False,
                "error_code": ErrorCode.NOT_FOUND.value["code"],
                "error_message": f"Failed to fetch completed tasks with task type {task_type}",
            }
    except Exception as e:
        logger.log(LogLevel.ERROR, f"An error occurred: {str(e)}")
        return {
            "status": False,
            "error_code": ErrorCode.GENERAL.value["code"],
            "error_message": str(e),
        }


def get_task_type_name_by_id(task_type_list: list, task_type_id: int) -> str:
    for task_type in task_type_list:
        if task_type.id == task_type_id:
            return task_type.name
    return ""  # Return an empty string if the task type ID is not found


def get_task_status_name_by_id(task_status_list: list, task_status_id: int) -> str:
    for task_status in task_status_list:
        if task_status.id == task_status_id:
            return task_status.name
    return ""  # Return an empty string if the task type ID is not found


# def md5_hash(input_string):
#     # Create an MD5 hash object
#     md5 = hashlib.md5()

#     # Update the hash object with the bytes of the input string
#     md5.update(input_string.encode("utf-8"))

#     # Get the hexadecimal representation of the hash
#     hashed_string = md5.hexdigest()

#     return hashed_string


# Run the FastAPI application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=host, port=port)