import pandas as pd
from strands import tool

from utils.aws_utils import load_project_csv, project_exists


@tool
def get_task_info(
        task_identifier: str, project_name: str, wbs_name: str = None) -> dict:
    """
    Procura os detalhes de uma atividade (tarefa) no cronograma.
d
    Args:
        task_identifier (str): O nome da tarefa (task_name) ou o código (task_code).".
        project_name (str): O nome do projeto para acessar o arquivo específico
        wbs_name (str, opcional): O nome ou código do pacote WBS para desempatar tarefas com o mesmo nome.


    Returns:
        Dict: Dicionário com os atributos da tarefa ou pedido de desambiguação.
    """

    # Pegar o nome dos projetos(São diretórios)
    if not project_name:
        return {"error": "Projeto não especificado"}
    if not project_exists(project_name):
        return {"error": f"Projeto '{project_name}' não encontrado."}

    try:
        # Transforma em dataframe
        df_task = load_project_csv(project_name, "TASK.csv")
        df_wbs = load_project_csv(project_name, "PROJWBS.csv")

    except FileNotFoundError as e:
        return {"error": str(e)}

    if df_task.empty or df_wbs.empty:
        return {"error": "Falha ao aceder aos ficheiros TASK.csv ou PROJWBS.csv"}

    # Fazemos um merge (join) das tarefas com a tabela WBS para ter o nome do pacote disponível
    df_merged = pd.merge(df_task, df_wbs, on='wbs_id',
                         how='left', suffixes=('', '_wbs'))

    # Filtrar pelo nome ou código da tarefa
    mask_task = (
        df_merged['task_name'].fillna('').str.lower()
        == task_identifier.lower()) | (
        df_merged['task_code'].fillna('').str.lower()
        == task_identifier.lower())

    resultado = df_merged[mask_task]

    if resultado.empty:
        return {"error": f"Tarefa '{task_identifier}' não encontrada no cronograma."}

    # Se o utilizador forneceu a WBS, filtramos novamente para desempatar
    if wbs_name:
        mask_wbs = (
            resultado['wbs_name'].str.contains(
                wbs_name, case=False, na=False)) | (
            resultado['wbs_short_name'].str.contains(
                wbs_name, case=False, na=False))
        resultado = resultado[mask_wbs]

        if resultado.empty:
            return {"error": f"A tarefa '{task_identifier}' não foi encontrada dentro do pacote WBS '{wbs_name}'."}

    # Avaliar quantas tarefas restaram
    if len(resultado) == 1:
        # Sucesso absoluto: encontrou apenas uma
        tarefa_dict = resultado.iloc[0].to_dict()
        return {k: v for k, v in tarefa_dict.items() if pd.notna(v)}

    # Pega as 5 primeiras para mostrar ao usuário (evita texto gigante)
    opcoes = resultado[['task_code', 'task_name', 'wbs_name']].head(
        5).to_dict('records')

    if wbs_name:
        mensagem_alerta = f"Mesmo filtrando pelo WBS '{wbs_name}', ainda encontrei {len(resultado)} tarefas com esse nome (provavelmente em áreas/fases diferentes)."
    else:
        mensagem_alerta = f"Foram encontradas {
            len(resultado)}  tarefas com o nome '{task_identifier} '."

    return {
        "alerta": mensagem_alerta,
        "acao_requerida": "Mostre as 'opcoes_encontradas' ao usuário e peça para ele copiar e colar o 'task_code' exato da tarefa que ele deseja.",
        "opcoes_encontradas": opcoes
    }
