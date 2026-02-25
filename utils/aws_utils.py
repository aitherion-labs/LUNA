from functools import lru_cache

import boto3
import pandas as pd
from botocore.exceptions import ClientError

BUCKET_NAME = "microgenesys-etl-files"

s3_client = boto3.client("s3")


def project_exists(project_name: str) -> bool:
    """
    Valida se o projeto existe verificando se o PROJECT.csv está presente.
    """
    try:
        s3_client.head_object(
            Bucket=BUCKET_NAME,
            Key=f"processed/{project_name}/csv_files/PROJECT.csv"
        )
        return True
    except ClientError:
        return False


@lru_cache(maxsize=10)
def load_project_csv(project_name: str, filename: str) -> pd.DataFrame:
    """
    Carrega qualquer CSV de um projeto do S3 (com cache de memória).
    """
    try:
        obj = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=f"processed/{project_name}/csv_files/{filename}"
        )
        return pd.read_csv(obj["Body"])
    except ClientError as e:
        raise FileNotFoundError(
            f"Arquivo {filename} não encontrado para o projeto {project_name}"
        ) from e
