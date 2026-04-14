import csv
import io
import json
import logging
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TARGET_TABLES = {"PROJECT", "PROJWBS", "TASK",
                 "TASKPRED", "RSRC", "CALENDAR", "ACTVCODE"}

s3_client = boto3.client('s3')


@dataclass
class TableData:
    cols: List[str]
    rows: List[List[str]] = field(default_factory=list)


@dataclass
class ParseStats:
    total_rows: int = 0
    padded_rows: int = 0
    truncated_rows: int = 0
    decode_replaced_lines: int = 0
    tables_seen: set = field(default_factory=set)

    def to_json(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "padded_rows": self.padded_rows,
            "truncated_rows": self.truncated_rows,
            "decode_replaced_lines": self.decode_replaced_lines,
            "tables_seen": sorted(list(self.tables_seen)),
        }


def split_tag(line: str) -> Tuple[str, List[str]]:
    parts = line.split("\t")
    return parts[0], parts[1:]


def pad_or_truncate(
        values: List[str],
        n_cols: int, stats: ParseStats) -> List[str]:
    if len(values) < n_cols:
        stats.padded_rows += 1
        values = values + [""] * (n_cols - len(values))
    elif len(values) > n_cols:
        stats.truncated_rows += 1
        values = values[:n_cols]
    return values


def parse_xer(lines_iterator: Iterator[str],
              target_tables: set) -> Tuple[Dict[str, TableData],
                                           ParseStats]:
    """Reconstrói tabelas do XER em memória lendo o iterador de linhas (Stream do S3)."""
    tables: Dict[str, TableData] = {}
    stats = ParseStats()
    current_table: Optional[str] = None
    current_cols: Optional[List[str]] = None
    drop_indices = set()

    for line in lines_iterator:
        if line.startswith("ERMHDR"):
            continue
        if "" in line:
            stats.decode_replaced_lines += 1

        tag, fields = split_tag(line)

        if tag == "%E":
            break

        if tag == "%T":
            if fields:
                current_table = fields[0]
                current_cols = None
                drop_indices = set()
                stats.tables_seen.add(current_table)
            continue

        if tag == "%F":
            if current_table is None:
                continue
            if current_table == "CALENDAR" and "clndr_data" in fields:
                idx = fields.index("clndr_data")
                drop_indices.add(idx)

            current_cols = [f for i, f in enumerate(
                fields) if i not in drop_indices]
            tables.setdefault(current_table, TableData(cols=current_cols))
            continue

        if tag == "%R":
            stats.total_rows += 1
            if current_table is None or not current_cols:
                continue
            if drop_indices:
                fields = [f for i, f in enumerate(
                    fields) if i not in drop_indices]

            values = pad_or_truncate(fields, len(current_cols), stats)

            if current_table in target_tables:
                tables.setdefault(current_table, TableData(
                    cols=current_cols)).rows.append(values)

    return tables, stats


def validate_dependencies(tables: Dict[str, TableData]) -> dict:
    """Verifica integridade referencial mínima entre TASKPRED e TASK."""
    if "TASK" not in tables or "TASKPRED" not in tables:
        return {"ok": False, "error": "Tabelas TASK e/ou TASKPRED não encontradas."}

    task = tables["TASK"]
    pred = tables["TASKPRED"]

    try:
        task_id_idx = task.cols.index("task_id")
        succ_idx = pred.cols.index("task_id")
        pred_idx = pred.cols.index("pred_task_id")
    except ValueError as e:
        return {"ok": False, "error": f"Coluna esperada não encontrada: {e}"}

    task_ids = {r[task_id_idx] for r in task.rows if r[task_id_idx]}
    missing_succ = sum(1 for r in pred.rows
                       if r[succ_idx] and r[succ_idx] not in task_ids)
    missing_pred = sum(1 for r in pred.rows
                       if r[pred_idx] and r[pred_idx] not in task_ids)

    return {
        "tasks_count": len(task.rows),
        "dependencies_count": len(pred.rows),
        "missing_successor_refs": missing_succ,
        "missing_predecessor_refs": missing_pred,
        "ok": (missing_succ == 0 and missing_pred == 0),
    }


def upload_string_to_s3(bucket: str, key: str, content: str):
    """Utilitário para subir strings (CSV/JSON) diretamente da RAM para o S3."""
    s3_client.put_object(Bucket=bucket, Key=key, Body=content.encode('utf-8'))


def export_csv_to_s3(
        bucket: str, base_prefix: str, table_name: str, table: TableData):
    csv_buffer = io.StringIO()
    w = csv.writer(csv_buffer)
    w.writerow(table.cols)
    w.writerows(table.rows)
    s3_key = f"{base_prefix}/csv_files/{table_name}.csv"
    upload_string_to_s3(bucket, s3_key, csv_buffer.getvalue())
    csv_buffer.close()


def lambda_handler(event, context):
    try:
        # Pega as informações do arquivo XER que disparou o evento
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        raw_key = event['Records'][0]['s3']['object']['key']

        xer_key = urllib.parse.unquote_plus(raw_key)

        # Ignora se não for arquivo .xer
        if not xer_key.lower().endswith('.xer'):
            return {"status": "Ignorado", "reason": "Não é um arquivo .xer"}

        # Define a pasta de saída baseada no nome do arquivo
        file_name = xer_key.split(
            '/')[-1].replace('.xer', '').replace('.XER', '')
        out_prefix = f"processed/{file_name}"

        logger.info(f"Iniciando conversão do arquivo: {xer_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=xer_key)

        # Cria um gerador que lê linha por linha diretamente do stream do S3
        def s3_lines_iterator():
            for raw_line in response['Body'].iter_lines():
                if raw_line:
                    yield raw_line.decode('utf-8', errors='replace').rstrip('\n')

        # Passa o iterador para a sua lógica de conversão
        tables, stats = parse_xer(s3_lines_iterator(), TARGET_TABLES)

        exported_counts = {}
        for t in sorted(TARGET_TABLES):
            if t in tables:
                exported_counts[t] = len(tables[t].rows)
                # Exporta CSV e JSON direto para o S3
                export_csv_to_s3(bucket_name, out_prefix, t, tables[t])

        dep_report = validate_dependencies(tables)

        summary = {
            "input": xer_key,
            "tables_exported": exported_counts,
            "parse_stats": stats.to_json(),
            "dependency_validation": dep_report,
        }

        # Salva os relatórios de summary e dependency
        upload_string_to_s3(bucket_name, f"{out_prefix}/dependency_validation.json",
                            json.dumps(dep_report, ensure_ascii=False, indent=2))
        upload_string_to_s3(
            bucket_name, f"{out_prefix}/summary.json", json.dumps(summary, ensure_ascii=False, indent=2))

        logger.info(f"Conversão finalizada com sucesso. Prefix: {out_prefix}")

        return {
            "statusCode": 200,
            "body": f"Arquivo {file_name} processado e exportado com sucesso."
        }

    except Exception as e:
        logger.error(f"Erro ao processar arquivo: {str(e)}", exc_info=True)
        raise e
