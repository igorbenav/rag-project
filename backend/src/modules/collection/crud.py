"""CRUD operations for collections."""

from fastcrud import FastCRUD

from .models import Collection

collection_crud: FastCRUD = FastCRUD(Collection)
