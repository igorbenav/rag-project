"""CRUD operations for chunks."""

from fastcrud import FastCRUD

from .models import Chunk

chunk_crud: FastCRUD = FastCRUD(Chunk)
