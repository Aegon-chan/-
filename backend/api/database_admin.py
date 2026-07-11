"""
Database Management API

Provides endpoints for browsing, querying, and managing database tables
from the frontend, so administrators can inspect and maintain data
without direct database access.
"""

from __future__ import annotations

import logging
import csv
import io
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
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



# === Batch Delete & Import schemas ===

class BatchDeleteRequest(BaseModel):
    ids: list[str] = Field(..., description="List of primary key values to delete")

class DateCondition(BaseModel):
    column: str = Field(..., description="Date column name")
    start: Optional[str] = Field(None, description="Start date (inclusive, ISO format)")
    end: Optional[str] = Field(None, description="End date (inclusive, ISO format)")
    before: Optional[str] = Field(None, description="Delete data before this date (exclusive)")

class ConditionDeleteRequest(BaseModel):
    date_condition: Optional[DateCondition] = Field(None, description="Date range filter")
    text_filter: Optional[str] = Field(None, description="Text search (applied to text columns)")
    dry_run: bool = Field(True, description="Preview mode: count only, no actual delete")

    @field_validator("date_condition")
    @classmethod
    def validate_date_condition(cls, v):
        if v is not None and not v.start and not v.end and not v.before:
            raise ValueError("At least one of start/end/before must be provided")
        return v

class DeleteResult(BaseModel):
    success: bool = True
    database: str = ""
    table: str = ""
    dry_run: bool = True
    matched_count: int = 0
    deleted_count: int = 0
    sample_rows: list[dict] = Field(default_factory=list)
    message: str = ""

class ImportPreviewResponse(BaseModel):
    success: bool = True
    database: str = ""
    table: str = ""
    total_rows: int = 0
    column_mapping: dict[str, str] = Field(default_factory=dict)
    missing_columns: list[str] = Field(default_factory=list)
    sample_rows: list[dict] = Field(default_factory=list)
    estimated_inserts: int = 0
    potential_issues: list[str] = Field(default_factory=list)

class ImportResponse(BaseModel):
    success: bool = True
    database: str = ""
    table: str = ""
    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list[dict] = Field(default_factory=list)
    message: str = ""

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
            result = conn.execute(sa_text("SELECT COUNT(*) FROM " + table))
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


def _validate_table(engine, table: str) -> list[str]:
    valid = _get_table_names(engine)
    if table not in valid:
        raise HTTPException(
            status_code=404,
            detail="Table '%s' not found. Available: %s" % (table, ", ".join(valid)),
        )
def _get_text_columns(columns: list[dict]) -> list[str]:
    return [c["name"] for c in columns if "CHAR" in c["type"].upper() or "TEXT" in c["type"].upper()]



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
        base = "FROM " + table
        params = {}
        text_cols = [c["name"] for c in columns if "CHAR" in c["type"].upper() or "TEXT" in c["type"].upper()]
        if search and text_cols:
            clauses = ['"%s" LIKE :search' % c for c in text_cols]
            base += " WHERE " + " OR ".join(clauses)
            params["search"] = "%%%s%%" % search
        count_sql = "SELECT COUNT(*) %s" % base
        total = conn.execute(sa_text(count_sql), params).scalar() or 0
        offset = (page - 1) * page_size
        order = pk_col if pk_col else '"%s"' % col_names[0]
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



@router.delete("/{database}/{table}/batch-delete", summary="Batch delete rows by IDs")
async def batch_delete(database: str, table: str, body: BatchDeleteRequest):
    if database not in ("main", "monitoring"):
        raise HTTPException(status_code=400, detail="database must be 'main' or 'monitoring'")
    engine = _get_engine(database)
    _validate_table(engine, table)
    pk_col = _get_table_pk(engine, table)
    if not pk_col:
        raise HTTPException(status_code=400, detail="Table '%s' has no primary key" % table)
    ids = body.ids
    if not ids:
        raise HTTPException(status_code=400, detail="ids list cannot be empty")
    with engine.begin() as conn:
        count_sql = sa_text('SELECT COUNT(*) FROM "%s" WHERE "%s" IN (%s)' % (
            table, pk_col, ",".join(":id%d" % i for i in range(len(ids)))))
        params = {"id%d" % i: v for i, v in enumerate(ids)}
        matched = conn.execute(count_sql, params).scalar() or 0
        if matched == 0:
            raise HTTPException(status_code=404, detail="No matching rows found for given IDs")
        delete_sql = sa_text('DELETE FROM "%s" WHERE "%s" IN (%s)' % (
            table, pk_col, ",".join(":id%d" % i for i in range(len(ids)))))
        result = conn.execute(delete_sql, params)
    return {"success": True, "database": database, "table": table,
            "matched_count": matched, "deleted_count": result.rowcount,
            "message": "Deleted %d rows from %s.%s" % (result.rowcount, database, table)}


@router.post("/{database}/{table}/delete-by-condition", summary="Delete rows by condition with dry-run")
async def delete_by_condition(database: str, table: str, body: ConditionDeleteRequest):
    if database not in ("main", "monitoring"):
        raise HTTPException(status_code=400, detail="database must be 'main' or 'monitoring'")
    engine = _get_engine(database)
    _validate_table(engine, table)
    columns = _get_columns(engine, table)
    col_names = [c["name"] for c in columns]
    clauses = []
    params = {}
    text_cols = _get_text_columns(columns)
    if body.date_condition:
        dc = body.date_condition
        if dc.column not in col_names:
            raise HTTPException(status_code=400, detail="Column '%s' not found in table" % dc.column)
        if dc.start:
            clauses.append('"%s" >= :date_start' % dc.column)
            params["date_start"] = dc.start
        if dc.end:
            clauses.append('"%s" <= :date_end' % dc.column)
            params["date_end"] = dc.end
        if dc.before:
            clauses.append('"%s" < :date_before' % dc.column)
            params["date_before"] = dc.before
    if body.text_filter and text_cols:
        or_clauses = ['"%s" LIKE :text_search' % c for c in text_cols]
        clauses.append("(" + " OR ".join(or_clauses) + ")")
        params["text_search"] = "%%%s%%" % body.text_filter
    if not clauses:
        raise HTTPException(status_code=400, detail="At least one condition must be provided")
    where_clause = " AND ".join(clauses)
    pk_col = _get_table_pk(engine, table)
    with engine.connect() as conn:
        count_sql = sa_text('SELECT COUNT(*) FROM "%s" WHERE %s' % (table, where_clause))
        matched = conn.execute(count_sql, params).scalar() or 0
        sample_rows = []
        if matched > 0:
            order = pk_col if pk_col else '"%s"' % col_names[0]
            sample_sql = sa_text('SELECT * FROM "%s" WHERE %s ORDER BY %s LIMIT 5' % (table, where_clause, order))
            sample_raw = conn.execute(sample_sql, params).fetchall()
            for row in sample_raw:
                r = dict(zip(col_names, row))
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()
                sample_rows.append(r)
    if body.dry_run or matched == 0:
        return DeleteResult(success=True, database=database, table=table,
                            dry_run=body.dry_run, matched_count=matched, deleted_count=0,
                            sample_rows=sample_rows,
                            message="Matched %d rows (dry_run=True, no deletion performed)" % matched)
    with engine.begin() as conn:
        delete_sql = sa_text('DELETE FROM "%s" WHERE %s' % (table, where_clause))
        result = conn.execute(delete_sql, params)
    return DeleteResult(success=True, database=database, table=table,
                        dry_run=False, matched_count=matched, deleted_count=result.rowcount,
                        sample_rows=sample_rows,
                        message="Deleted %d rows from %s.%s" % (result.rowcount, database, table))


@router.post("/{database}/{table}/import/preview", summary="Preview CSV/XLSX data import")
async def preview_table_import(database: str, table: str,
                                file: UploadFile = File(..., description="CSV or XLSX file")):
    if database not in ("main", "monitoring"):
        raise HTTPException(status_code=400, detail="database must be 'main' or 'monitoring'")
    engine = _get_engine(database)
    _validate_table(engine, table)
    columns = _get_columns(engine, table)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    try:
        import pandas as pd
        from io import BytesIO
        ext = Path(file.filename or "data.csv").suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(BytesIO(content), encoding="utf-8", low_memory=False)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(BytesIO(content), engine="openpyxl" if ext != ".xls" else "xlrd")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format: %s" % ext)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to parse file: %s" % e)
    if df.empty:
        raise HTTPException(status_code=400, detail="File contains no data rows")
    db_col_names = {c["name"].lower(): c["name"] for c in columns}
    col_mapping = {}
    missing = []
    for file_col in df.columns:
        col_clean = file_col.strip().lower()
        if col_clean in db_col_names:
            col_mapping[file_col] = db_col_names[col_clean]
        else:
            found = False
            for dn_lower, dn in db_col_names.items():
                if col_clean in dn_lower or dn_lower in col_clean:
                    col_mapping[file_col] = dn
                    found = True
                    break
            if not found:
                missing.append(file_col)
    sample = df.head(5).fillna("").to_dict(orient="records")
    sample_clean = []
    for row in sample:
        clean = {}
        for k, v in row.items():
            clean[k] = str(v)[:80]
        sample_clean.append(clean)
    issues = []
    required_cols = [c["name"] for c in columns if not c.get("nullable", True) and not c.get("primary_key", False)]
    for rc in required_cols:
        if rc.lower() not in [v.lower() for v in col_mapping.values()]:
            if rc not in ("id", "created_at", "updated_at"):
                issues.append("Required column '%s' not found in file" % rc)
    return ImportPreviewResponse(
        success=True, database=database, table=table,
        total_rows=len(df), column_mapping=col_mapping,
        missing_columns=missing, sample_rows=sample_clean,
        estimated_inserts=len(df), potential_issues=issues)


@router.post("/{database}/{table}/import", summary="Import CSV/XLSX data into table")
async def import_table_data(database: str, table: str,
                             file: UploadFile = File(..., description="CSV or XLSX file"),
                             skip_errors: bool = Form(True, description="Skip rows with parse errors")):
    if database not in ("main", "monitoring"):
        raise HTTPException(status_code=400, detail="database must be 'main' or 'monitoring'")
    engine = _get_engine(database)
    _validate_table(engine, table)
    columns = _get_columns(engine, table)
    db_col_names = {c["name"].lower(): c["name"] for c in columns}
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "data.csv").suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    try:
        import pandas as pd
        ext = Path(file.filename or "data.csv").suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(tmp_path, encoding="utf-8", low_memory=False)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(tmp_path, engine="openpyxl" if ext != ".xls" else "xlrd")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format: %s" % ext)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to parse file: %s" % e)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if df.empty:
        raise HTTPException(status_code=400, detail="File contains no data rows")
    col_mapping = {}
    for file_col in df.columns:
        col_clean = file_col.strip().lower()
        if col_clean in db_col_names:
            col_mapping[file_col] = db_col_names[col_clean]
        else:
            for dn_lower, dn in db_col_names.items():
                if col_clean in dn_lower or dn_lower in col_clean:
                    col_mapping[file_col] = dn
                    break
    if not col_mapping:
        raise HTTPException(status_code=400,
                            detail="No columns matched. File columns: %s. Table columns: %s" %
                            (list(df.columns), list(db_col_names.values())))
    db_target_cols = list(col_mapping.values())
    file_source_cols = list(col_mapping.keys())
    placeholders = ", ".join(":p%d" % i for i in range(len(db_target_cols)))
    quoted_cols = ', '.join('"%s"' % c for c in db_target_cols)
    insert_sql = sa_text('INSERT INTO "%s" (%s) VALUES (%s)' % (table, quoted_cols, placeholders))
    pk_col = _get_table_pk(engine, table)
    imported = 0
    skipped = 0
    errors = []
    BATCH_SIZE = 200
    with engine.begin() as conn:
        batch_params = []
        for idx, row in df.iterrows():
            row_num = idx + 2
            try:
                params = {}
                valid = True
                for j, file_col in enumerate(file_source_cols):
                    val = row.get(file_col)
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        val = None
                    elif hasattr(val, "isoformat"):
                        val = val.isoformat()
                    else:
                        val = str(val)
                    db_col = db_target_cols[j]
                    if db_col == pk_col and (val is None or val == "" or val == "nan"):
                        valid = False
                        break
                    params["p%d" % j] = val
                if not valid:
                    if not skip_errors:
                        continue
                    skipped += 1
                    continue
                batch_params.append(params)
                if len(batch_params) >= BATCH_SIZE:
                    conn.execute(insert_sql, batch_params)
                    imported += len(batch_params)
                    batch_params = []
            except Exception as e:
                skipped += 1
                errors.append({"row": row_num, "reason": str(e)})
                if not skip_errors:
                    break
        if batch_params:
            conn.execute(insert_sql, batch_params)
            imported += len(batch_params)
    total = len(df)
    total_skipped = total - imported
    return ImportResponse(
        success=True, database=database, table=table,
        total_rows=total, imported=imported, skipped=total_skipped,
        errors=errors[:50],
        message="Imported %d rows into %s.%s. %d skipped." % (imported, database, table, total_skipped))


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
