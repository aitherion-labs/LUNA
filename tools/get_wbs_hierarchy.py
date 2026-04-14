from typing import Optional

from strands import tool

from utils.aws_utils import load_project_csv, project_exists


@tool
def get_wbs_hierarchy(
        project_name: str,
        wbs_name: Optional[str] = None,
        wbs_id: Optional[str] = None) -> dict:
    """
    Busca a hierarquia de um pacote WBS no Primavera P6.
    Retorna os detalhes da WBS, o nome do seu pacote Pai e a lista de pacotes Filhos.
    """

    if not project_name:
        return {"error": "Projeto não especificado"}
    if not project_exists(project_name):
        return {"error": f"Projeto '{project_name}' não encontrado."}
    if not wbs_name and not wbs_id:
        return {"error": "Deve informar o wbs_name ou o wbs_id."}

    try:
        # Forçar conversão de IDs para string para evitar erros de tipagem no Pandas
        df_wbs = load_project_csv(project_name, "PROJWBS.csv")
        df_wbs['wbs_id'] = df_wbs['wbs_id'].astype(str)
        df_wbs['parent_wbs_id'] = df_wbs['parent_wbs_id'].astype(str)
    except FileNotFoundError as e:
        return {"error": str(e)}

    if df_wbs.empty:
        return {"error": "Falha ao aceder ao ficheiro PROJWBS.csv"}

    # Busca exata pelo ID
    if wbs_id:
        resultado = df_wbs[df_wbs['wbs_id'] == str(wbs_id)]

    # Busca aberta pelo nome
    else:
        mask_wbs = (
            df_wbs['wbs_name'].str.contains(
                wbs_name, case=False, na=False)) | (
            df_wbs['wbs_short_name'].str.contains(
                wbs_name, case=False, na=False))
        resultado = df_wbs[mask_wbs]

    if resultado.empty:
        termo = wbs_id if wbs_id else wbs_name
        return {"error": f"WBS '{termo}' não encontrada no cronograma."}

    if len(resultado) == 1:
        target_wbs = resultado.iloc[0]
        target_id = target_wbs['wbs_id']
        parent_id = target_wbs['parent_wbs_id']

        # Acha o pai
        parent_row = df_wbs[df_wbs['wbs_id'] == parent_id]
        parent_name = parent_row.iloc[0][
            'wbs_name'] if not parent_row.empty else "Nenhum (Projeto Raiz)"

        # Acha os filhos
        children_rows = df_wbs[df_wbs['parent_wbs_id'] == target_id]
        children_list = children_rows['wbs_name'].tolist()

        wbs_dict = target_wbs.dropna().to_dict()

        return {
            "wbs_solicitada": target_wbs['wbs_name'],
            "wbs_pai": parent_name,
            "wbs_filhas": children_list if children_list else "Nenhuma WBS filha.",
            "detalhes_da_wbs": wbs_dict
        }

    opcoes_estruturadas = []

    # Itera sobre os primeiros 5 resultados para montar as opções
    for _, row in resultado.head(5).iterrows():
        # Busca o nome do pai para dar contexto ao utilizador
        parent_row = df_wbs[df_wbs['wbs_id'] == row['parent_wbs_id']]
        parent_name = parent_row.iloc[0]['wbs_name'] if not parent_row.empty else "Raiz"

        opcoes_estruturadas.append({
            "wbs_id": row['wbs_id'],
            "wbs_name": row['wbs_name'],
            "pertence_ao_pai": parent_name
        })

    return {
        "alerta": f"opcoes_encontradas: Foram encontradas {len(resultado)} WBS com o nome '{wbs_name}'.",
        "acao_requerida": "Mostre as opções de 'pertence_ao_pai' ao usuário. Quando o usuário responder, CHAME ESTA TOOL NOVAMENTE passando EXCLUSIVAMENTE o parâmetro 'wbs_id' da opção escolhida.",
        "opcoes_encontradas": opcoes_estruturadas
    }
