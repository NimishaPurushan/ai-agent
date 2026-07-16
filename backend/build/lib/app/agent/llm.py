"""Shared LLM + embeddings factory (cached)."""
from functools import lru_cache
from app.core.config import get_settings

from azure.identity import ClientSecretCredential, get_bearer_token_provider
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

DEFAULT_COGNITIVE_SERVICES_SCOPE = (
    "https://cognitiveservices.azure.com/.default"
)

@lru_cache
def get_chat_llm():
    settings = get_settings()

    token_provider = get_token_provider(settings)

    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment_name,
        api_version=settings.azure_openai_api_version,
        azure_ad_token_provider=token_provider,
        temperature=0.2,
        streaming=True,
    )



@lru_cache
def get_embeddings() -> AzureOpenAIEmbeddings:
    settings = get_settings()

    token_provider = get_token_provider(settings)

    return AzureOpenAIEmbeddings(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_embedding_deployment_name,
        api_version=settings.azure_openai_api_version,
        azure_ad_token_provider=token_provider,
        dimensions=1024,
    )


def get_token_provider(settings=None):
    credential = get_credential(settings)

    token_provider = get_bearer_token_provider(
        credential,
        DEFAULT_COGNITIVE_SERVICES_SCOPE
    )

    return token_provider


def get_credential(settings=None) -> ClientSecretCredential:

    return ClientSecretCredential(
        tenant_id=settings.azure_openai_tenant_id,
        client_id=settings.azure_openai_client_id,
        client_secret=settings.azure_openai_client_secret,
    )