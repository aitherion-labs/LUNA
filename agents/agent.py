import boto3
from strands import Agent
from strands.models import BedrockModel
from strands.session.s3_session_manager import S3SessionManager

from config.settings import settings
from tools.gerador_senhas import gerador_de_senhas

system_prompt = """
Você é um agente de IA útil com acesso a uma ferramenta para gerar senhas fortes.
- Ferramenta: `gerador_de_senhas` para geração de senhas.

Instruções importantes de resposta:
- Responda APENAS com a resposta final ao usuário, em linguagem clara e direta.
- NÃO inclua pensamentos internos, raciocínio passo a passo, explicações de processo, nem tags como <thinking> ou similares.
- Se precisar justificar algo, use no máximo uma frase breve e objetiva, sem revelar seu raciocínio interno.
- Quando apropriado, utilize a ferramenta disponível para atender ao pedido.
"""


def default_agent(session_id: str, model_id: str) -> Agent:
    session = boto3.Session(
        region_name=settings.aws_region,
        profile_name=settings.aws_profile,
    )

    session_manager = S3SessionManager(
        session_id=session_id,
        bucket=settings.s3_bucket_sessions,
        prefix="orchestrator/",
        boto_session=session,
    )

    model = BedrockModel(
        model_id=model_id,
        temperature=0.2,
        top_p=0.8,
        boto_session=session,
    )

    user_credentials = {
        "user_id": "api_user",
        "session_id": session_id,
    }

    my_agent = Agent(
        model=model,
        system_prompt=system_prompt,
        state=user_credentials,
        session_manager=session_manager,
        tools=[gerador_de_senhas],
    )

    return my_agent
