"""Unidad de trabajo con contexto de autorización RLS.

``SET LOCAL app.user_id`` solo vive dentro de la transacción en curso (spec R3 §9.4). Tras un
``commit``/``rollback`` el contexto desaparece: ``UnitOfWork`` lo restablece explícitamente para
el siguiente tramo de la misma solicitud. Si el contexto no se restablece, RLS no devuelve filas
(falla segura).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


class UnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self.session = Session(engine, expire_on_commit=False)
        self.user_id: UUID | None = None

    # -- contexto RLS -----------------------------------------------------------------------
    def set_user(self, user_id: UUID) -> None:
        if not isinstance(user_id, UUID):  # nunca interpolar texto arbitrario en SET LOCAL
            raise TypeError("user_id debe ser uuid.UUID")
        self.user_id = user_id
        self._apply_context()

    def _apply_context(self) -> None:
        if self.user_id is not None:
            # SET LOCAL no admite parámetros enlazados; el UUID tipado garantiza el formato.
            self.session.execute(text(f"SET LOCAL app.user_id = '{self.user_id}'"))

    # -- transacciones ----------------------------------------------------------------------
    def commit(self) -> None:
        self.session.commit()
        self._apply_context()

    def rollback(self) -> None:
        self.session.rollback()
        self._apply_context()

    def close(self) -> None:
        self.session.rollback()  # nada sin confirmar sobrevive; devuelve la conexión limpia
        self.session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


@contextmanager
def unit_of_work(engine: Engine, user_id: UUID | None = None) -> Iterator[UnitOfWork]:
    """Para código fuera de FastAPI (worker, CLI, pruebas)."""
    uow = UnitOfWork(engine)
    try:
        if user_id is not None:
            uow.set_user(user_id)
        yield uow
    finally:
        uow.close()
