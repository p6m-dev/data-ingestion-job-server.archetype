from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import os
from dotenv import load_dotenv
import requests
import json
from fastapi import Query, Form, HTTPException
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from utils import get_env_var


Base = declarative_base()


class Database:
    def __init__(self, db_host, db_name, db_user, db_password):
        self.db_host = db_host
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.engine = self.create_engine()
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def create_engine(self):
        return create_engine(
            f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}/{self.db_name}",
            echo=True,
        )

    def init_database(self):
        Base.metadata.create_all(bind=self.engine)


# SQLAlchemy models
class TaskStatus(Base):
    __tablename__ = "task_status"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)


class TaskType(Base):
    __tablename__ = "task_type"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)


class TaskQueue(Base):
    __tablename__ = "task_queue"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(256), nullable=True)
    task_type_id = Column(Integer, ForeignKey("task_type.id"), nullable=False)
    claimed_time = Column(DateTime, nullable=True)
    claimed_by_agent = Column(String(256), nullable=True)
    task_status_id = Column(Integer, ForeignKey("task_status.id"), nullable=False)
    message = Column(String(2048), nullable=True)
    completed_time = Column(DateTime, nullable=True)
    failed_time = Column(DateTime, nullable=True)
    original_documents_retrieved = Column(Integer, nullable=True, default=0)
    text_documents_retrieved = Column(Integer, nullable=True, default=0)
    requested_by_user = Column(String(256), nullable=True)
    notes = Column(String(2048), nullable=True)
    job_progress_metrics = Column(JSON, nullable=True, default={})
    object_storage_key_for_results = Column(String(256), nullable=True)
    parameter_checksum = Column(String(256), nullable=True)
    revision = Column(String(256), nullable=True)


def get_db():
    db = Database(
        db_host=get_env_var("DB_HOST"),
        db_name=get_env_var("DB_NAME"),
        db_user=get_env_var("DB_USER"),
        db_password=get_env_var("DB_PASSWORD"),
    )
    db.init_database()
    return db.SessionLocal()
