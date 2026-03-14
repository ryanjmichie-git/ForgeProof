"""In-memory todo storage service."""

from __future__ import annotations

from src.models.todo import Todo


class TodoService:
    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id = 1

    def create(self, title: str) -> Todo:
        todo = Todo(id=self._next_id, title=title)
        self._todos[todo.id] = todo
        self._next_id += 1
        return todo

    def get(self, todo_id: int) -> Todo | None:
        return self._todos.get(todo_id)

    def list_all(self) -> list[Todo]:
        return sorted(self._todos.values(), key=lambda t: t.id)

    def complete(self, todo_id: int) -> Todo | None:
        todo = self._todos.get(todo_id)
        if todo:
            todo.completed = True
        return todo

    def delete(self, todo_id: int) -> bool:
        return self._todos.pop(todo_id, None) is not None
