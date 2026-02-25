import pandas as pd
from strands import tool

from tools.get_task_info import get_task_info
from utils.aws_utils import load_project_csv


@tool
def get_task_relationships(task_identifier: str, project_name: str) -> dict:
    """Busca predecessoras e sucessoras de uma tarefa, incluindo os seus nomes reais."""
    tarefa_info = get_task_info(task_identifier, project_name)

    if "error" in tarefa_info or "alerta" in tarefa_info:
        return tarefa_info

    task_id = tarefa_info.get("task_id")
    if not task_id:
        return {"error": "task_id não encontrado na tarefa."}

    try:
        # Transforma em dataframe
        df_pred = load_project_csv(project_name, "TASKPRED.csv")
        df_task = load_project_csv(project_name, "TASK.csv")

    except FileNotFoundError as e:
        return {"error": str(e)}

    if df_pred.empty or df_task.empty:
        return {"error": "Falha ao acessar arquivos no S3."}

    # Pegamos apenas as colunas que importam do TASK.csv para não pesar a memória
    df_task_nomes = df_task[['task_id', 'task_code', 'task_name']]

    # SUCESSORAS: A nossa tarefa é a predecessora (pred_task_id). Queremos saber quem é a task_id.
    sucs_df = df_pred[df_pred['pred_task_id'] == task_id]
    sucs_merged = pd.merge(sucs_df, df_task_nomes, on='task_id', how='left')

    # PREDECESSORAS: A nossa tarefa é a sucessora (task_id). Queremos saber quem é a pred_task_id.
    preds_df = df_pred[df_pred['task_id'] == task_id]
    preds_merged = pd.merge(
        preds_df, df_task_nomes, left_on='pred_task_id', right_on='task_id',
        how='left')

    return {
        "tarefa_analisada": tarefa_info,
        "predecessoras": preds_merged.to_dict('records'),
        "sucessoras": sucs_merged.to_dict('records')
    }
