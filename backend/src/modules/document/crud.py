"""CRUD operations for documents."""

from fastcrud import FastCRUD

from .models import Document

document_crud: FastCRUD = FastCRUD(Document)
