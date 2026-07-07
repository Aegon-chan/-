"""
Database Management API

Provides endpoints for browsing, querying, and managing database tables
from the frontend, so administrators can inspect and maintain data
without direct database access.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect, text as sa_text

from backend.db.session import sync_engine
from backend.db.monitoring_session import sync_engine as monitoring_sync_engine

logger = logging.getLogger("research_agent.api.database_admin")

router = APIRouter()


class TableInfo(BaseModel):
    name: str
    row_count: int
    columns: list[dict] = Field(default_factory=list, description="Column name & type")
    database: str = "main"


class TableListResponse(BaseModel):
    tables: list[TableInfo]
    total_tables: int


class RowResponse(BaseModel):
    rows: list[dict]
    total: int
    page: int
    page_size: int
    columns: list[dict]


class QueryRequest(BaseModel):
    sql: str = Field(..., description="SELECT SQL to execute (read-only)")
    database: str = Field("main", description="'main' or 'monitoring'")


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int


class DbStats(BaseModel):
    database: str
    table_count: int
    total_rows: int
    file_size_mb: float


class StatsResponse(BaseModel):
    databases: list[DbStats]


def _get_engine(db_name: str = "main"):
    if db_name == "monitoring":
        return monitoring_sync_engine
    return sync_engine


def _get_table_names(engine) -> list[str]:
    insp = sa_inspect(engine)
    all_tables = insp.get_table_names()
    return [t for t in all_tables if not t.startswith("alembic_")]


def _get_columns(engine, table: str) -> list[dict]:
    insp = sa_inspect(engine)
    cols = []
    try:
        for col in insp.get_columns(table):
            cols.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col.get("primary_key", False),
            })
    except Exception as e:
        logger.warning("Could not inspect columns for %s: %s", table, e)
    return cols


def _get_row_count(engine, table: str) -> int:
    try:
        with engine.connect() as conn:
            result = conn.execute(sa_text('SELECT COUNT(*) FROM "%s"' % table))
            return result.scalar() or 0
    except Exception as e:
        logger.warning("Could not count rows for %s: %s", table, e)
        return 0


def _get_table_pk(engine, table: str) -> str | None:
    cols = _get_columns(engine, table)
    for col in cols:
        if col.get("primary_key"):
            return col["name"]
    return None


def _validate_table(engine, table: str) -> None:
    valid = _get_table_names(engine)
    if table not in valid:
        raise HTTPException(
            status_code=404,
            detail="Table '%s' not found. Available: %s" % (table, ", ".join(valid)),
        )


# ── Endpoints ────────────────────────────────────────────────────────────
# NOTE: Specific routes MUST be declared before catch-all parameterized routes

@router.get("/tables", response_model=TableListResponse, summary="List all tables")
async def list_tables():
    tables: list[TableInfo] = []
    for db_name, engine in [("main", sync_engine), ("monitoring", monitoring_sync_engine)]:
        try:
            names = _get_table_names(engine)
        except Exception as e:
            logger.warning("Cannot inspect %s database: %s", db_name, e)
            continue
        for name in names:
            cols = _get_columns(engine, name)
            count = _get_row_count(engine, name)
            tables.append(TableInfo(name=name, row_count=count, columns=cols, database=db_name))
    tables.sort(key=lambda t: (t.database, t.name))
    return TableListResponse(tables=tables, total_tables=len(tables))


@router.get("/stats/all", response_model=StatsResponse, summary="Database statistics")
async def get_stats():
    databases = []
    for db_name, engine in [("main", sync_engine), ("monitoring", monitoring_sync_engine)]:
        try:
            names = _get_table_names(engine)
            total_rows = sum(_get_row_count(engine, t) for t in names)
            file_size_mb = 0.0
            try:
                url = str(engine.url)
                if url.startswith("sqlite:///"):
                    db_path = url.replace("sqlite:///", "")
                    import os
                    if os.path.exists(db_path):
                        file_size_mb = os.path.getsize(db_path) / (1024 * 1024)
            except Exception:
                pass
            databases.append(DbStats(
                database=db_name,
                table_count=len(names),
                total_rows=total_rows,
                file_size_mb=round(file_size_mb, 2),
            ))
        except Exception as e:
            logger.warning("Cannot get stats for %s database: %s", db_name, e)
    return StatsResponse(databases=databases)


@router.get("/query/preview", summary="Preview available tables for querying")
async def preview_query():
    """Lightweight endpoint to preview available tables and schemas."""
    tables = []
    for db_name, engine in [("main", sync_engine), ("monitoring", monitoring_sync_engine)]:
        try:
            names = _get_table_names(engine)
            for name in names:
                tables.append({"database": db_name, "table": name, "columns": _get_columns(engine, name)})
        except Exception:
            pass
    return {"tables": tables}


@router.get("/{database}/{table}", response_model=RowResponse, summary="Browse table rows")
async def browse_table(
    database: str,
    table: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Rows per page"),
    search: str = Query("", description="Optional search filter (applied to text columns)"),
):
    if database not in ("main", "monitoring"):
        raise HTTPException(status_code=400, detail="database must be 'main' or 'monitoring'")
    engine = _get_engine(database)
    _validate_table(engine, table)
    columns = _get_columns(engine, table)
    col_names = [c["name"] for c in columns]
    pk_col = _get_table_pk(engine, table)
    with engine.connect() as conn:
        base = 'FROM "%s"' % table
        params = {}
        text_cols = [c["name"] for c in columns if "CHAR" in c["type"].upper() or "TEXT" in c["type"].upper()]
        if search and text_cols:
            clauses = ['"%s" LIKE :search' % c for c in text_cols]
            base += " WHERE " + " OR ".join(clauses)
            params["search"] = "%%%s%%" % search
        count_sql = "SELECT COUNT(*) %s" % base
        total = conn.execute(sa_text(count_sql), params).scalar() or 0
        offset = (page - 1) * page_size
        order = '"%s"' % pk_col if pk_col else '"%s"' % col_names[0]
        data_sql = "SELECT * %s ORDER BY %s LIMIT :limit OFFSET :offset" % (base, order)
        params["limit"] = page_size
        params["offset"] = offset
        rows_raw = conn.execute(sa_text(data_sql), params).fetchall()
    rows = [dict(zip(col_names, row)) for row in rows_raw]
    for row in rows:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
    return RowResponse(rows=rows, total=total, page=page, page_size=page_size, columns=columns)


@router.delete("/{database}/{table}/{row_id}", summary="Delete a row")
async def delete_row(database: str, table: str, row_id: str):
    if database not in ("main", "monitoring"):
        raise HTTPException(status_code=400, detail="database must be 'main' or 'monitoring'")
    engine = _get_engine(database)
    _validate_table(engine, table)
    pk_col = _get_table_pk(engine, table)
    if not pk_col:
        raise HTTPException(status_code=400, detail="Table '%s' has no detectable primary key" % table)
    with engine.begin() as conn:
        sql = sa_text('DELETE FROM "%s" WHERE "%s" = :rid' % (table, pk_col))
        result = conn.execute(sql, {"rid": row_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Row with %s='%s' not found" % (pk_col, row_id))
    return {"deleted": True, "table": table, "id": row_id}


@router.post("/query", response_model=QueryResponse, summary="Execute read-only SQL query")
async def execute_query(body: QueryRequest):
    sql_stripped = body.sql.strip().lower()
    if not sql_stripped.startswith("select") and not sql_stripped.startswith("with"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    engine = _get_engine(body.database)
    try:
        with engine.connect() as conn:
            result = conn.execute(sa_text(body.sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=400, detail="Query failed: %s" % e)
    for row in rows:
        for i, val in enumerate(row):
            if hasattr(val, "isoformat"):
                row[i] = val.isoformat()
    return QueryResponse(columns=columns, rows=rows, row_count=len(rows))