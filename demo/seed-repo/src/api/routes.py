"""Todo API routes."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.services.todo_service import TodoService

app = FastAPI(title="Todo API", version="0.1.0")
service = TodoService()


class CreateTodoRequest(BaseModel):
    title: str


class TodoResponse(BaseModel):
    id: int
    title: str
    completed: bool
    created_at: str


@app.get("/todos", response_model=list[TodoResponse])
def list_todos():
    return [TodoResponse(**t.__dict__) for t in service.list_all()]


@app.post("/todos", response_model=TodoResponse, status_code=201)
def create_todo(req: CreateTodoRequest):
    todo = service.create(req.title)
    return TodoResponse(**todo.__dict__)


@app.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int):
    todo = service.get(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse(**todo.__dict__)


@app.post("/todos/{todo_id}/complete", response_model=TodoResponse)
def complete_todo(todo_id: int):
    todo = service.complete(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse(**todo.__dict__)


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    if not service.delete(todo_id):
        raise HTTPException(status_code=404, detail="Todo not found")
